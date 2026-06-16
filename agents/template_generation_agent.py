"""
Template Generation Agent — 独立的模板生成Agent

职责：
1. 通过LLM生成通道2模板（DSL + Python函数代码）
2. 维护长期记忆（已生效模板、被拒模板+原因、参数经验、设计模式）
3. 写入 PostgreSQL 模板库 pending 队列供风控团队审核

两种触发方式：
- 任务驱动：任务列表新建"模板生成"任务
- 对话驱动：AgentChat页面用户提出需求 → agent_chat.py 调用本Agent

输出格式（写入 templates.status=pending）：
{
  "template_id": "T016",           // 自动分配
  "template_name": "特征英文名",     // snake_case
  "template_name_cn": "特征中文名",
  "dimension": "applist|fdc|base|behavior",
  "complexity": "L1|L2|L3",
  "description": "特征描述",
  "dsl": "DSL表达式",
  "dsl_description": "DSL说明",
  "parameter_space": {...},
  "python_function": "calc_xxx",
  "python_module": "channel1_calculators",
  "formula_template": "公式模板",
  "examples": [...],
  "python_code": "完整Python计算代码",
  "design_reason": "设计理由",
  "_promotion_status": "pending",
}
"""

import json
import logging
import os
import re
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.llm_client import LLMClient
from backend.app.database import SessionLocal
from backend.services.template_library import (
    ACTIVE_STATUS,
    PENDING_STATUS,
    active_dsl_set,
    list_dimensions,
    list_templates,
    next_template_id,
    upsert_template_from_payload,
)

logger = logging.getLogger(__name__)


class TemplateGenerationAgent:
    """模板生成Agent — 生成通道2模板的DSL和Python代码"""

    def __init__(self):
        self.llm_client = LLMClient()

        # 路径配置
        self.base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.channel1_calculators_path = os.path.join(
            self.base_dir, "outputs", "feature_code", "channel1_calculators.py"
        )
        self.knowledge_dir = os.path.join(
            self.base_dir, "outputs", "template_knowledge"
        )
        self.rejected_path = os.path.join(
            self.knowledge_dir, "rejected_templates.json"
        )
        self.param_exp_path = os.path.join(
            self.knowledge_dir, "parameter_experience.json"
        )
        self.design_patterns_path = os.path.join(
            self.knowledge_dir, "design_patterns.json"
        )
        # User-uploaded knowledge extractions
        self.user_knowledge_extracted_dir = os.path.join(
            self.base_dir, "data", "user_knowledge_extracted"
        )

        # 确保知识目录存在
        os.makedirs(self.knowledge_dir, exist_ok=True)

    # ============================================================
    # 公共入口
    # ============================================================

    def generate_template(self, user_request: str, dimension: str = "") -> Dict:
        """生成一个通道2模板

        Args:
            user_request: 用户描述的需求
            dimension: 可选维度过滤 (applist/fdc/base/behavior)

        Returns:
            包含执行结果信息的字典
        """
        # 1. 加载长期记忆
        channel1_templates = self._load_channel1_templates()
        channel1_code = self._load_channel1_code()
        rejected = self._load_rejected()
        param_exp = self._load_param_experience()
        design_patterns = self._load_design_patterns()
        next_id = self._get_next_template_id(channel1_templates)
        existing_names = self._get_existing_names(channel1_templates)

        # 2. 整理知识上下文
        knowledge = self._build_knowledge_context(
            channel1_templates, channel1_code, rejected,
            param_exp, design_patterns, next_id, existing_names,
            dimension, user_request
        )

        # 3. 调用LLM
        system_prompt = knowledge["system_prompt"]
        result = self._call_llm(system_prompt, user_request)

        if not result:
            return {
                "success": False,
                "error": "LLM未能生成有效模板",
                "templates": []
            }

        # 4. 保存到 PostgreSQL pending 队列
        saved = self._save_to_pending(result)

        return {
            "success": True,
            "templates": saved,
            "count": len(saved),
            "message": f"生成了 {len(saved)} 个模板，已加入待审核列表"
        }

    # ============================================================
    # 长期记忆加载
    # ============================================================

    def _load_channel1_templates(self) -> Dict:
        """从 PostgreSQL 加载已生效的通道1模板。"""
        db = SessionLocal()
        try:
            templates = []
            for t in list_templates(db, status=ACTIVE_STATUS):
                templates.append({
                    "template_id": t.template_id,
                    "template_name": t.template_name,
                    "template_name_cn": t.template_name_cn or "",
                    "dimension": t.dimension.dimension_code if t.dimension else "",
                    "complexity": t.complexity or "",
                    "description": t.description or "",
                    "dsl": t.dsl or "",
                    "dsl_description": t.dsl_description or "",
                    "parameter_space": t.parameter_space or {},
                    "python_function": t.python_function or "",
                    "python_module": t.python_module or "",
                    "formula_template": t.formula_template or "",
                    "examples": t.examples or [],
                })
            dimensions = [
                {
                    "dimension_id": d.dimension_id or d.dimension_code,
                    "dimension_name": d.dimension_code,
                    "dimension_name_cn": d.dimension_name_cn,
                    "description": d.description,
                    "templates": [
                        t["template_name"]
                        for t in templates
                        if t.get("dimension") == d.dimension_code
                    ],
                }
                for d in list_dimensions(db)
            ]
            return {
                "templates": templates,
                "dimensions": dimensions,
                "total_templates": len(templates),
            }
        finally:
            db.close()

    def _load_channel1_code(self) -> str:
        """加载通道1计算函数的Python代码"""
        if os.path.exists(self.channel1_calculators_path):
            try:
                with open(self.channel1_calculators_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                pass
        return ""

    def _load_rejected(self) -> List[Dict]:
        """加载被拒模板历史"""
        if os.path.exists(self.rejected_path):
            try:
                with open(self.rejected_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _load_param_experience(self) -> List[Dict]:
        """加载参数经验"""
        if os.path.exists(self.param_exp_path):
            try:
                with open(self.param_exp_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _load_design_patterns(self) -> List[Dict]:
        """加载设计模式"""
        if os.path.exists(self.design_patterns_path):
            try:
                with open(self.design_patterns_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _get_next_template_id(self, channel1: Dict) -> str:
        """获取下一个可用的template_id"""
        db = SessionLocal()
        try:
            return next_template_id(db)
        finally:
            db.close()

    def _get_existing_names(self, channel1: Dict) -> List[str]:
        """获取已存在的模板名称列表"""
        names = []
        for t in channel1.get("templates", []):
            names.append(t.get("template_name", ""))
        return names

    def _load_user_knowledge(self) -> str:
        """Load user-uploaded knowledge extractions and format for context."""
        if not os.path.isdir(self.user_knowledge_extracted_dir):
            return ""
        parts = []
        for fname in sorted(os.listdir(self.user_knowledge_extracted_dir)):
            if not fname.endswith(".extraction.json"):
                continue
            fpath = os.path.join(self.user_knowledge_extracted_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    ext = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            if ext.get("error"):
                continue

            file_type = ext.get("file_type", "?")
            summary = ext.get("overall_summary", "")
            lines = [f"- [{file_type}] {ext.get('filename', fname)}: {summary}"]

            if file_type == "code":
                for fn in ext.get("functions", [])[:3]:
                    params = ", ".join(p.get("name", "") for p in fn.get("parameters", []))
                    lines.append(f"  · {fn.get('name','?')}({params}) → [{fn.get('computation_pattern','')}]")
            elif file_type == "doc":
                for ins in ext.get("key_insights", [])[:3]:
                    lines.append(f"  · 发现: {ins}")
                for r in ext.get("business_rules", [])[:2]:
                    lines.append(f"  · 规则: {r}")
            elif file_type == "table":
                for s in ext.get("statistical_patterns", [])[:3]:
                    lines.append(f"  · {s.get('metric','')}={s.get('value','')}")

            parts.append("\n".join(lines))

        return "\n".join(parts) if parts else ""

    # ============================================================
    # 知识上下文构建
    # ============================================================

    def _build_knowledge_context(
        self,
        channel1_templates: Dict,
        channel1_code: str,
        rejected: List[Dict],
        param_exp: List[Dict],
        design_patterns: List[Dict],
        next_id: str,
        existing_names: List[str],
        dimension: str,
        user_request: str,
    ) -> Dict:
        """构建LLM的system prompt上下文"""

        # 已生效模板摘要
        templates_summary = []
        for t in channel1_templates.get("templates", []):
            templates_summary.append(
                f"- {t.get('template_id')} [{t.get('template_name')}] "
                f"({t.get('template_name_cn', '')}) — {t.get('dimension')} — "
                f"DSL: {t.get('dsl')} — {t.get('description', '')}"
            )
        templates_text = "\n".join(templates_summary) if templates_summary else "（暂无）"

        # 维度信息
        dims_text = ""
        for d in channel1_templates.get("dimensions", []):
            dims_text += (
                f"- {d['dimension_id']} {d['dimension_name_cn']}({d['dimension_name']}): "
                f"{d['description']}: "
                f"{', '.join(d.get('templates', []))}\n"
            )

        # 被拒模板
        rejected_text = ""
        if rejected:
            for r in rejected[-10:]:  # 最近10条
                rejected_text += (
                    f"- {r.get('template_name', '?')}: {r.get('reason', '')} "
                    f"(拒绝时间: {r.get('date', '')})\n"
                )

        # 参数经验
        param_text = ""
        if param_exp:
            for p in param_exp[-10:]:
                param_text += (
                    f"- {p.get('template', '?')}: range={p.get('range', {})}, "
                    f"notes={p.get('notes', '')}\n"
                )

        # 设计模式
        pattern_text = ""
        if design_patterns:
            for p in design_patterns[-5:]:
                pattern_text += (
                    f"- {p.get('name', '')}: {p.get('description', '')}\n"
                )

        # Python代码片段 —— 展示一个示例函数的格式（不塞全部955行）
        code_sample = self._extract_code_sample(channel1_code)

        # ── User knowledge extractions ──
        user_knowledge_text = self._load_user_knowledge()

        dimension_filter = f"（当前请求维度: {dimension}）" if dimension else "（不限维度）"

        system_prompt = f"""你是印尼现金贷风控特征挖掘系统的模板设计专家。你的职责是根据用户需求，生成新的特征计算模板。

## 当前时间
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 已有的通道1模板（已生效，不可重复设计）
{channel1_templates.get('total_templates', 0)}个模板，分为7个维度：

{dims_text}

各模板详情：
{templates_text}

{dimension_filter}

## 历史被拒模板（避免重复犯同样错误）
{rejected_text if rejected_text else "（暂无被拒记录）"}

## 参数设计经验
{param_text if param_text else "（暂无参数经验）"}

## 历史设计模式参考
{pattern_text if pattern_text else "（暂无历史模式）"}

## Python计算函数代码格式参考（函数名、参数结构、防穿越机制）
```python
{code_sample}
```

## 已存在的模板名称（不可重复）
{', '.join(existing_names) if existing_names else '暂无'}

## 用户上传知识文档（可参考其中的业务规则和计算模式）
{user_knowledge_text if user_knowledge_text else '（暂无用户上传知识）'}

## 输出要求

请生成新的特征计算模板。输出JSON格式：

```json
[
  {{
    "template_name": "英文特征名，snake_case，不含具体业务值",
    "template_name_cn": "中文特征名",
    "dimension": "维度（volume/structure/change/position/consistency）",
    "complexity": "复杂度（L1/L2/L3）",
    "description": "模板的计算逻辑描述（不含具体业务值，抽象到通用计算语义）",
    "dsl": "DSL表达式，如 count(field_set, window, cond)",
    "dsl_description": "DSL的计算逻辑说明",
    "parameter_space": {{
      "source": {{"type": "string", "description": "数据源标识", "values": ["applist", "fdc_pinjaman"]}},
      "window": {{"type": "int", "description": "回溯窗口天数", "values": [7, 30, 90]}},
      ...其他参数
    }},
    "python_function": "Python函数名",
    "formula_template": "近{{window}}天...的公式中文描述",
    "examples": ["示例1", "示例2", "示例3"],
    "python_code": "完整的Python计算函数代码（含防穿越机制、从channel1_calculators的辅助函数导入、docstring）",
    "design_reason": "设计理由"
  }}
]
```

## 关键约束

1. **不可重复**：template_name和template_id不能与已有模板重复
2. **template_id**：新模板从 {next_id} 开始编号
3. **防穿越**：所有Python代码必须使用 apply_time_dt 参数作为基准时间
4. **数据源**：支持的数据源包括 applist（应用列表）、fdc_inquiry（FDC查询记录）、fdc_pinjaman（FDC贷款记录）、base（用户基础信息）
5. **代码风格**：Python函数代码应与 channel1_calculators.py 中的风格一致，使用同样的辅助函数（_filter_by_time, _get_event_time 等）
6. **DSL风格**：DSL表达式应与已有模板风格一致，清晰表达计算逻辑
7. **parameter_space**：参数空间必须尽量提供可执行取值列表 `values`（或 `enum/options/choices`），供后续确定性参数展开使用；不要只写 type/description
8. **仅生成1-3个模板**：除非用户明确要求更多，每次生成1-3个最相关的模板
9. **输出仅包含JSON数组**，不要额外说明文字
10. **模板必须剥离业务含义**：从用户需求中识别出的风险信号（如"赌博应用占比高"、"现金贷多头借贷"）应该抽象为通用计算结构，把具体的业务值（赌博、现金贷等）放到 parameter_space 中。模板名、描述、DSL 中不能包含具体业务词（如 high_risk、gambling、loan）。parameter_space 中可包含 category 参数用于传递具体业务值。
11. **DSL 不能与已生效模板重复**：生成模板前，对照已有的通道1模板 DSL 列表（见"已有的通道1模板"一节），确保新模板的 DSL 计算模式未被覆盖。如果用户需求的计算逻辑已经能用某个通道1模板的 DSL 参数化表达，则不需要创建新模板。
"""

        return {
            "system_prompt": system_prompt,
        }

    def _extract_code_sample(self, code: str) -> str:
        """从channel1_calculators.py中提取一个示例函数的代码"""
        if not code:
            return "# No existing calculator code"
        # 提取前几个函数的代码作为参考
        lines = code.split("\n")
        sample_lines = []
        func_count = 0
        in_func = False
        for line in lines:
            if line.startswith("def ") and not line.startswith("def _") and func_count < 2:
                in_func = True
                func_count += 1
            if in_func:
                sample_lines.append(line)
                if func_count >= 2 and line.strip() == "":
                    break
        text = "\n".join(sample_lines)
        if len(text) > 2000:
            text = text[:2000] + "\n    ..."
        return text

    # ============================================================
    # LLM调用
    # ============================================================

    def _call_llm(self, system_prompt: str, user_request: str) -> List[Dict]:
        """调用LLM生成模板"""
        try:
            response = self.llm_client.chat([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_request},
            ], temperature=0.3, max_tokens=8000)
        except Exception as e:
            print(f"  LLM调用失败: {e}")
            return []

        # 解析JSON
        return self._parse_response(response)

    def _parse_response(self, response: str) -> List[Dict]:
        """解析LLM返回的JSON"""
        # 提取JSON块
        json_blocks = re.findall(r'```json\s*(\[[\s\S]*?\])\s*```', response, re.DOTALL)
        if not json_blocks:
            json_blocks = re.findall(r'```\s*(\[[\s\S]*?\])\s*```', response, re.DOTALL)
        if not json_blocks:
            # 尝试直接解析整段回复
            try:
                data = json.loads(response.strip())
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                pass
            return []

        for block in json_blocks:
            try:
                data = json.loads(block)
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                continue
        return []

    # ============================================================
    # 保存
    # ============================================================

    def _save_to_pending(self, templates: List[Dict]) -> List[Dict]:
        """将生成的模板保存到 PostgreSQL pending 队列（自动去重）"""
        if not templates:
            return []

        saved = []
        db = SessionLocal()
        try:
            existing_names = {
                t.template_name
                for t in list_templates(db)
                if t.template_name
            }
            ch1_dsls_normalized = active_dsl_set(db)

            for i, tmpl in enumerate(templates):
                tmpl_name = tmpl.get("template_name", f"template_{i + 1}")
                if tmpl_name in existing_names:
                    continue

                dsl = tmpl.get("dsl", "")
                if dsl:
                    norm = re.sub(r"\b\d+\b", "*", dsl)
                    norm = re.sub(r"\s+", "", norm)
                    if norm in ch1_dsls_normalized:
                        logger.info(
                            "Skipping template '%s' — DSL '%s' normalized to '%s' matches channel1",
                            tmpl_name, dsl, norm,
                        )
                        continue

                entry = {
                    "template_id": tmpl.get("template_id") or next_template_id(db),
                    "template_name": tmpl_name,
                    "template_name_cn": tmpl.get("template_name_cn", ""),
                    "dimension": tmpl.get("dimension", ""),
                    "complexity": tmpl.get("complexity", "L1"),
                    "description": tmpl.get("description", ""),
                    "dsl": tmpl.get("dsl", ""),
                    "dsl_description": tmpl.get("dsl_description", ""),
                    "parameter_space": tmpl.get("parameter_space", {}),
                    "python_function": tmpl.get("python_function", ""),
                    "python_module": "channel1_calculators",
                    "formula_template": tmpl.get("formula_template", ""),
                    "examples": tmpl.get("examples", []),
                    "python_code": tmpl.get("python_code", ""),
                    "design_reason": tmpl.get("design_reason", ""),
                    "source": "模板生成",
                    "_promotion_status": "pending",
                    "created_at": datetime.now().isoformat(),
                }
                row = upsert_template_from_payload(
                    db,
                    entry,
                    status=PENDING_STATUS,
                    source_channel=2,
                    source="模板生成",
                    commit=False,
                )
                db.flush()
                existing_names.add(tmpl_name)
                saved.append(row.to_dict())

            db.commit()
            return saved
        finally:
            db.close()

    # ============================================================
    # 知识积累 —— 供外部调用（被拒记录、参数经验更新）
    # ============================================================

    def record_rejection(self, template_name: str, reason: str):
        """记录被拒模板"""
        rejected = self._load_rejected()
        rejected.append({
            "template_name": template_name,
            "reason": reason,
            "date": datetime.now().isoformat(),
        })
        # 最多保留100条
        if len(rejected) > 100:
            rejected = rejected[-100:]
        with open(self.rejected_path, "w", encoding="utf-8") as f:
            json.dump(rejected, f, ensure_ascii=False, indent=2)

    def record_param_experience(self, template: str, param_range: Dict, notes: str):
        """记录参数经验"""
        exp = self._load_param_experience()
        # 去重：同模板名替换
        exp = [e for e in exp if e.get("template") != template]
        exp.append({
            "template": template,
            "range": param_range,
            "notes": notes,
            "date": datetime.now().isoformat(),
        })
        with open(self.param_exp_path, "w", encoding="utf-8") as f:
            json.dump(exp, f, ensure_ascii=False, indent=2)


def generate_templates(user_request: str, dimension: str = "") -> Dict:
    """便捷调用入口"""
    agent = TemplateGenerationAgent()
    return agent.generate_template(user_request, dimension)


if __name__ == "__main__":
    # 测试
    import sys
    req = sys.argv[1] if len(sys.argv) > 1 else "设计一个统计用户申请时GPS与IP所在城市是否一致的模板"
    dim = sys.argv[2] if len(sys.argv) > 2 else ""
    result = generate_templates(req, dim)
    print(json.dumps(result, ensure_ascii=False, indent=2))
