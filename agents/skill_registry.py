"""
Skill注册表 + post_hook校验引擎

管理所有Skill的注册、调用、校验、重试。
每个Skill可注册多个post_hook check，校验LLM输出质量。

内置check函数:
- compile_check: Python代码能否编译
- anti_travel_check: 是否使用了applyTime而非datetime.now
- dsl_syntax_check: DSL语法是否合法
- param_completeness: 参数是否完整
"""

import logging
import ast
import re
from typing import Callable, Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SkillResult:
    """Skill执行结果"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    retryable: bool = True          # 是否可重试
    hook_errors: List[str] = field(default_factory=list)  # post_hook校验失败记录


@dataclass
class HookCheck:
    """单个post_hook校验项"""
    name: str
    check_func: Callable[[Any], Optional[str]]  # 接收data，返回None=通过，str=错误信息
    retryable: bool = True                       # 此check是否可重试


class SkillRegistry:
    """Skill注册表"""

    def __init__(self):
        self._skills: Dict[str, Callable] = {}
        self._hooks: Dict[str, List[HookCheck]] = {}
        self.max_retries = 3

    def register_skill(self, name: str, func: Callable, hooks: List[HookCheck] = None):
        """注册一个Skill及其post_hook

        Args:
            name: Skill名称
            func: Skill执行函数
            hooks: post_hook校验列表
        """
        self._skills[name] = func
        if hooks:
            self._hooks[name] = hooks
        logger.info(f"Skill注册: {name} (hooks: {len(hooks or [])}个)")

    def execute(self, name: str, **kwargs) -> SkillResult:
        """执行Skill（含重试逻辑）

        Args:
            name: Skill名称
            **kwargs: 传递给Skill函数的参数

        Returns:
            SkillResult
        """
        if name not in self._skills:
            return SkillResult(success=False, error=f"Skill '{name}' 未注册", retryable=False)

        func = self._skills[name]
        hooks = self._hooks.get(name, [])

        for attempt in range(1, self.max_retries + 1):
            # 执行skill
            try:
                raw_result = func(**kwargs)
            except Exception as e:
                logger.error(f"Skill '{name}' 执行异常 (尝试{attempt}/{self.max_retries}): {e}")
                if attempt < self.max_retries:
                    continue
                return SkillResult(success=False, error=str(e), retryable=True)

            # 执行post_hook校验
            hook_errors = []
            all_retryable = True
            for check in hooks:
                error_msg = check.check_func(raw_result)
                if error_msg:
                    hook_errors.append(f"[{check.name}] {error_msg}")
                    if not check.retryable:
                        all_retryable = False
                    logger.warning(f"Skill '{name}' post_hook校验失败: [{check.name}] {error_msg}")

            if not hook_errors:
                # 全部通过
                return SkillResult(success=True, data=raw_result)

            # 有校验失败
            if not all_retryable:
                # 包含不可重试的check，直接返回失败
                return SkillResult(
                    success=False,
                    data=raw_result,
                    error="; ".join(hook_errors),
                    retryable=False,
                    hook_errors=hook_errors
                )

            if attempt < self.max_retries:
                logger.info(f"Skill '{name}' 校验失败，第{attempt}次重试...")
                # 把错误信息注入kwargs，skill可通过此信息自我修正
                import inspect
                if 'hook_feedback' in inspect.signature(func).parameters:
                    kwargs['hook_feedback'] = hook_errors
            else:
                return SkillResult(
                    success=False,
                    data=raw_result,
                    error=f"重试{self.max_retries}次后仍校验失败: {'; '.join(hook_errors)}",
                    retryable=True,
                    hook_errors=hook_errors
                )

        return SkillResult(success=False, error=f"Skill '{name}' 执行失败", retryable=True)

    def get_skill_names(self) -> List[str]:
        """获取所有已注册Skill名称"""
        return list(self._skills.keys())


# 全局Skill注册表实例
registry = SkillRegistry()


def register_skill(name: str, hooks: List[HookCheck] = None):
    """装饰器方式注册Skill"""
    def decorator(func):
        registry.register_skill(name, func, hooks)
        return func
    return decorator


# ============================================================
# 内置 post_hook check 函数
# ============================================================

def check_python_compile(python_code: str) -> Optional[str]:
    """检查Python代码能否编译

    可重试: True — LLM看到编译错误可自行修正
    """
    try:
        ast.parse(python_code)
        return None
    except SyntaxError as e:
        return f"Python编译错误: {e.msg} (行{e.lineno}, 列{e.offset})"


def check_anti_time_travel(python_code: str) -> Optional[str]:
    """检查是否使用了applyTime（而非datetime.now）做数据过滤

    关键检查项:
    1. 代码中不应该出现 `datetime.now()` 作为数据过滤基准
    2. 应该出现 `apply_time` 或 `applyTime` 作为过滤条件

    可重试: True — LLM看到反馈后可添加applyTime参数
    """
    # 检查是否包含 datetime.now()
    now_patterns = [
        r'datetime\.now\(\)',
        r'datetime\.datetime\.now\(\)',
    ]
    for pattern in now_patterns:
        if re.search(pattern, python_code):
            return f"使用了 {pattern} ，数据过滤应使用applyTime而非当前时间（防穿越）"

    # 检查是否包含 apply_time 或 applyTime
    if 'apply_time' not in python_code and 'applyTime' not in python_code:
        return "代码中未使用 apply_time/applyTime 参数（防穿越基线）"

    return None


def check_dsl_syntax(dsl_expression: str) -> Optional[str]:
    """检查DSL语法是否合法

    支持的DSL模式:
    - count(...), distinct(...), decayed_sum(...)
    - proportion 格式: A / B
    - entropy|gini|cv(...)
    - overlap(...)
    - period_compare: (A / B) - 1
    - slope(...)
    - max_daily(...) > threshold * avg_daily(...)
    - percent_rank(...)
    - ratio(...), abs_diff(...), year_diff(...)
    - mismatch_count(...)
    - shared_value_count(...)
    - isolation_score(...)

    可重试: True — LLM看到语法错误可修正
    """
    if not dsl_expression or not isinstance(dsl_expression, str):
        return "DSL表达式为空"

    valid_patterns = [
        r'^count\(', r'^distinct\(', r'^decayed_sum\(',
        r'^entropy\(', r'^gini\(', r'^cv\(',
        r'^overlap\(',
        r'^slope\(',
        r'^max_daily\(',
        r'^percent_rank\(',
        r'^ratio\(', r'^abs_diff\(', r'^year_diff\(',
        r'^mismatch_count\(',
        r'^shared_value_count\(',
        r'^isolation_score\(',
        r'^\(\s*\w+\(.*\)\s*/\s*\w+\(.*\)\s*\)\s*-\s*1\s*$',  # (count(A)/count(B))-1
        r'>\s*\d+\s*\*',     # > threshold * avg (spike)
    ]

    stripped = dsl_expression.strip()
    if not any(re.match(p, stripped) for p in valid_patterns):
        return f"DSL语法无法识别: {dsl_expression[:100]}"

    return None


def check_param_completeness(params: Dict, required_keys: List[str]) -> Optional[str]:
    """检查参数是否完整

    不可重试 — 参数缺失通常是业务逻辑问题，LLM无法自行判断要填什么
    """
    if not params:
        return "参数为空"

    missing = [k for k in required_keys if k not in params]
    if missing:
        return f"缺少必要参数: {missing}"

    return None
