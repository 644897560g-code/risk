"""
Code AST Verifier - 成品代码质量验证器

职责：
1. 解析 FeatureCalculator.calculate_all 方法的AST
2. 逐特征验证每个特征值是否是通道1模板函数计算的结果
3. 列出违反项（特征名 + 问题行号 + 详细说明）

检测流程：
1. 从 return dict 获取每个特征名 → 变量名
2. 追溯变量在 calculate_all 中的赋值语句
3. 分析 RHS：模板函数调用 ✅ | 占位符 0.0 ⚪ | 手写代码 ❌
"""

import ast
import json
import logging
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# 已知的通道路1模板函数名（全部17个）
KNOWN_TEMPLATE_FUNCTIONS: Set[str] = {
    'calc_count', 'calc_distinct_count', 'calc_decayed_sum',
    'calc_proportion', 'calc_proportion_by_category',
    'calc_concentration', 'calc_concentration_by_category',
    'calc_overlap', 'calc_period_compare', 'calc_trend',
    'calc_spike', 'calc_percentile', 'calc_deviation',
    'calc_anomaly', 'calc_declared_vs_actual',
    'calc_cross_discrepancy', 'calc_identity_cluster',
}


def _get_var_assignments(function_node: ast.FunctionDef) -> Dict[str, ast.AST]:
    """从函数AST中提取所有变量的赋值语句

    返回: {变量名: RHS节点}
    """
    assignments = {}
    for node in ast.walk(function_node):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments[target.id] = node.value
    return assignments


def _is_template_function_call(node: ast.AST) -> bool:
    """检查AST节点是否为模板函数调用"""
    if not isinstance(node, ast.Call):
        return False
    # 直接名称: calc_count(...)
    if isinstance(node.func, ast.Name):
        return node.func.id in KNOWN_TEMPLATE_FUNCTIONS
    return False


def _is_placeholder(node: ast.AST) -> bool:
    """检查是否为占位符值 0.0 或 0"""
    return isinstance(node, ast.Constant) and (node.value == 0 or node.value == 0.0)


def _is_handwritten_code(node: ast.AST) -> bool:
    """检测手写代码模式"""
    # 列表/集合/字典推导式
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
        return True
    # sum(genexpr) 或 len(listcomp)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id in ('sum', 'len', 'max', 'min'):
            for arg in node.args:
                if isinstance(arg, (ast.GeneratorExp, ast.ListComp)):
                    return True
                if isinstance(arg, ast.Name) and isinstance(arg.ctx, ast.Load):
                    # 可能是 sum(counts.values()) — 追不到了，宽松处理
                    pass
    # self._filter_window 等辅助方法调用
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if isinstance(node.func.value, ast.Name) and node.func.value.id == 'self':
            return True
    # dict 推导相关的模式
    if isinstance(node, ast.Dict):
        for k, v in zip(node.keys, node.values):
            if v is None:
                continue
            # dict comprehension style
    return False


def _analyze_rhs(node: ast.AST) -> str:
    """分析RHS节点的模式，返回描述字符串"""
    # 变量引用: name → 继续追溯
    if isinstance(node, ast.Name):
        return f"变量引用: {node.id}"
    # 模板函数调用
    if _is_template_function_call(node):
        return "✅ 模板函数"
    # 占位符
    if _is_placeholder(node):
        return "⚪ 占位符"
    # 手写代码
    if _is_handwritten_code(node):
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            return "🔴 推导式（手写代码）"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            return f"🔴 sum/len/max(...) 手写代码"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            return f"🔴 self.{node.func.attr}() 手写代码"
        return "🔴 手写代码"
    # 其他
    return f"其他: {type(node).__name__}"


def verify_code(code: str, design_doc: Optional[Dict] = None) -> Dict:
    """验证成品代码的模板函数使用情况

    Args:
        code: 完整的 Python 源码字符串
        design_doc: 特征设计文档（含 template_id），可选

    Returns:
        {pass, total_features, compliant, violations, details}
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {'pass': False, 'total_features': 0, 'compliant': 0,
                'violations': [{'feature_name': '<syntax_error>', 'line_no': e.lineno or 0,
                                'problem': f"语法错误: {e}", 'severity': 'violation', 'template_id': None}],
                'details': f"❌ 语法错误: {e}"}

    # 从设计文档提取 template_id 映射
    template_map: Dict[str, str] = {}
    if design_doc:
        for feat in design_doc.get('features', []):
            name = feat.get('feature_name', '')
            tid = feat.get('template_id', '')
            if name:
                template_map[name] = tid

    # 查找 FeatureCalculator.calculate_all 方法
    calculate_all_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'calculate_all':
            calculate_all_node = node
            break

    if not calculate_all_node:
        return {'pass': False, 'total_features': 0, 'compliant': 0,
                'violations': [{'feature_name': '<missing_method>', 'line_no': 0,
                                'problem': "未找到 FeatureCalculator.calculate_all 方法",
                                'severity': 'violation', 'template_id': None}],
                'details': "❌ 未找到 calculate_all 方法"}

    # 获取函数内所有变量赋值
    assignments = _get_var_assignments(calculate_all_node)

    # 找到 return dict
    return_dict = None
    for node in ast.walk(calculate_all_node):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
            return_dict = node.value
            break

    if not return_dict:
        return {'pass': False, 'total_features': 0, 'compliant': 0,
                'violations': [{'feature_name': '<missing_return>', 'line_no': 0,
                                'problem': "calculate_all 未返回 dict",
                                'severity': 'violation', 'template_id': None}],
                'details': "❌ calculate_all 未返回 dict"}

    violations = []
    compliant = 0
    total = len(return_dict.keys)

    for key_node, val_node in zip(return_dict.keys, return_dict.values):
        if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
            feature_name = key_node.value
        else:
            feature_name = f"<unnamed_{getattr(key_node, 'lineno', 0)}>"

        tid = template_map.get(feature_name, None)

        # RHS 可能是一个变量名 → 追溯在函数体中的赋值
        rhs_node = val_node
        if isinstance(val_node, ast.Name):
            var_name = val_node.id
            if var_name in assignments:
                rhs_node = assignments[var_name]
            else:
                violations.append({
                    'feature_name': feature_name,
                    'line_no': getattr(val_node, 'lineno', 0),
                    'problem': f"变量 {var_name} 未在 calculate_all 中赋值",
                    'severity': 'violation',
                    'template_id': tid,
                })
                continue

        # 分析 RHS
        if _is_template_function_call(rhs_node):
            compliant += 1
            continue

        if _is_placeholder(rhs_node):
            violations.append({
                'feature_name': feature_name,
                'line_no': getattr(key_node, 'lineno', 0),
                'problem': _analyze_rhs(rhs_node),
                'severity': 'placeholder',
                'template_id': tid,
            })
            continue

        violations.append({
            'feature_name': feature_name,
            'line_no': getattr(key_node, 'lineno', 0),
            'problem': _analyze_rhs(rhs_node),
            'severity': 'violation',
            'template_id': tid,
        })

    actual_violations = [v for v in violations if v['severity'] == 'violation']
    placeholders = [v for v in violations if v['severity'] == 'placeholder']

    # 构建可读报告
    lines = []
    lines.append(f"特征总数: {total}")
    lines.append(f"  ✅ 合规（模板函数调用）: {compliant}")
    lines.append(f"  🔴 手写代码: {len(actual_violations)}")
    lines.append(f"  ⚪ 占位符: {len(placeholders)}")
    if compliant > 0:
        pct = compliant / total * 100 if total > 0 else 0
        lines.append(f"  模板函数使用率: {pct:.0f}%")

    if violations:
        lines.append(f"\n违反详情:")
        for v in violations:
            tag = "🔴" if v['severity'] == 'violation' else "⚪"
            tid_str = f" [{v.get('template_id', '?')}]" if v.get('template_id') else ""
            lines.append(f"  {tag} line {v['line_no']:>4} | {v['feature_name']}{tid_str}: {v['problem']}")

    passed = len(actual_violations) == 0

    return {
        'pass': passed,
        'total_features': total,
        'compliant': compliant,
        'violations': violations,
        'details': '\n'.join(lines),
    }


def run(code_path: str, design_doc_path: Optional[str] = None) -> Dict:
    """从文件路径运行验证"""
    with open(code_path, 'r', encoding='utf-8') as f:
        code = f.read()

    design_doc = None
    if design_doc_path and os.path.exists(design_doc_path):
        try:
            with open(design_doc_path, 'r', encoding='utf-8') as f:
                design_doc = json.load(f)
        except Exception as e:
            logger.warning(f"  加载设计文档失败: {e}")

    return verify_code(code, design_doc)


if __name__ == '__main__':
    import sys, os
    code_path = sys.argv[1] if len(sys.argv) > 1 else 'outputs/feature_code/features_calculator_v2.py'
    design_path = None
    if len(sys.argv) > 2:
        design_path = sys.argv[2]
    result = run(code_path, design_path)
    print(result['details'])
    print(f"\n总体判定: {'✅ 通过' if result['pass'] else '❌ 不通过'}")
