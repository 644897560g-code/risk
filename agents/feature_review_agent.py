"""
Feature Review Agent - 特征工程代码审核

职责：
1. 语法合法性检查（Python语法是否正确）
2. 逻辑正确性审核（防穿越、边界条件、计算逻辑）
3. 循环修正机制（发现问题后返回修正建议）
4. 生成审核报告

输入：生成的特征计算代码
输出：审核结果 + 修正建议
"""

import ast
import json
import os
import sys
from typing import Dict, List, Optional, Tuple

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from utils.llm_client import LLMClient


class FeatureReviewAgent:
    """特征工程代码审核Agent"""

    def __init__(self):
        self.llm_client = LLMClient()
        self.feature_doc = None
        self.generated_code = None
        self.code_path = None

    def load_feature_design(self, path='outputs/feature_design/feature_design_doc.json'):
        """加载特征设计文档（用于对照验证）"""
        with open(path, 'r', encoding='utf-8') as f:
            self.feature_doc = json.load(f)
        print(f"Loaded {len(self.feature_doc['features'])} features")

    def load_generated_code(self, path='outputs/feature_code/features_calculator_v2.py'):
        """加载生成的特征计算代码"""
        self.code_path = path
        with open(path, 'r', encoding='utf-8') as f:
            self.generated_code = f.read()
        print(f"Loaded code: {path} ({len(self.generated_code)} chars)")

    def review_syntax(self) -> Tuple[bool, List[str]]:
        """
        检查Python语法合法性

        Returns:
            (是否通过, 错误列表)
        """
        print("\n" + "=" * 70)
        print("1. 语法合法性检查")
        print("=" * 70)

        try:
            ast.parse(self.generated_code)
            print("   ✅ 语法检查通过")
            return True, []
        except SyntaxError as e:
            errors = [f"Line {e.lineno}: {e.msg}"]
            print(f"   ❌ 语法错误: {errors[0]}")
            return False, errors

    def review_logic(self) -> Tuple[bool, List[str]]:
        """
        检查逻辑正确性

        Returns:
            (是否通过, 问题列表)
        """
        print("\n" + "=" * 70)
        print("2. 逻辑正确性审核")
        print("=" * 70)

        issues = []

        # 检查1: 防穿越机制
        anti_time_travel_check = self._check_anti_time_travel()
        if not anti_time_travel_check[0]:
            issues.extend(anti_time_travel_check[1])

        # 检查2: 应用分类动态提取
        category_check = self._check_category_extraction()
        if not category_check[0]:
            issues.extend(category_check[1])

        # 检查3: 安全除法
        div_check = self._check_safe_division()
        if not div_check[0]:
            issues.extend(div_check[1])

        # 检查4: FDC字段正确性
        fdc_check = self._check_fdc_fields()
        if not fdc_check[0]:
            issues.extend(fdc_check[1])

        # 检查5: applist双时间过滤
        applist_check = self._check_applist_filter()
        if not applist_check[0]:
            issues.extend(applist_check[1])

        if issues:
            print(f"   ❌ 发现 {len(issues)} 个逻辑问题")
            for issue in issues:
                print(f"     - {issue}")
            return False, issues
        else:
            print("   ✅ 逻辑检查通过")
            return True, []

    def _check_anti_time_travel(self) -> Tuple[bool, List[str]]:
        """检查防穿越机制"""
        issues = []
        code = self.generated_code

        # 检查是否使用了applyTime（排除注释）
        code_no_comments = '\n'.join(
            line for line in code.split('\n')
            if not line.strip().startswith('#')
        )

        if 'applyTime' not in code_no_comments and 'apply_time' not in code_no_comments:
            issues.append("缺少applyTime基准点")

        # 检查是否有时间过滤逻辑
        if 'inTime' not in code and 'upTime' not in code:
            issues.append("applist缺少时间过滤（inTime/upTime）")

        if 'tgl_penyaluran_dana' not in code:
            issues.append("FDC缺少放款日期过滤")

        # 检查是否使用了当前时间（禁止）- 只看代码行，不看注释
        if 'datetime.now()' in code_no_comments or 'datetime.today()' in code_no_comments:
            issues.append("禁止使用当前系统时间（应使用applyTime）")

        return len(issues) == 0, issues

    def _check_category_extraction(self) -> Tuple[bool, List[str]]:
        """检查应用分类是否动态提取"""
        issues = []
        code = self.generated_code

        # 检查是否有硬编码的STANDARD_CATEGORIES（这是不允许的）
        hardcoded_patterns = [
            "STANDARD_CATEGORIES = {",
            "STANDARD_CATEGORIES={",
        ]
        for pattern in hardcoded_patterns:
            if pattern in code:
                issues.append(f"发现硬编码标准类别: {pattern}（应动态提取）")

        # 检查是否有动态提取机制（必须）
        if '_extract_standard_categories' not in code:
            issues.append("缺少动态类别提取方法 _extract_standard_categories")

        # 检查是否使用了硬编码的业务规则类别列表（这是允许的，但应有注释说明）
        # 如 high_risk_cats, loan_cats 等，这些是业务规则，不是标准类别
        # 只要有 _extract_standard_categories 方法，就认为标准类别是动态提取的
        # 硬编码的业务规则列表（如 high_risk_cats = ['gambling', 'cash_loan', ...]）是允许的

        return len(issues) == 0, issues

    def _check_safe_division(self) -> Tuple[bool, List[str]]:
        """检查安全除法"""
        issues = []
        code = self.generated_code

        # 检查是否有安全除法
        if '_safe_div' not in code and 'safe_div' not in code:
            issues.append("缺少安全除法函数")

        # 检查是否有除0保护
        if 'denominator != 0' not in code and 'if denominator' not in code:
            issues.append("缺少除0保护")

        return len(issues) == 0, issues

    def _check_fdc_fields(self) -> Tuple[bool, List[str]]:
        """检查FDC字段正确性"""
        issues = []
        code = self.generated_code

        # 错误的字段名
        wrong_fields = [
            ('last_3days', '3_hari'),
            ('last_7days', '7_hari'),
            ('last_30days', '30_hari'),
            ("platform_aktif', {}).get('count'", "platform_aktif', {}).get('jumlahPlatformAktif'"),
        ]
        for wrong, correct in wrong_fields:
            if wrong in code:
                issues.append(f"错误的FDC字段: '{wrong}' 应改为 '{correct}'")

        return len(issues) == 0, issues

    def _check_applist_filter(self) -> Tuple[bool, List[str]]:
        """检查applist双时间过滤"""
        issues = []
        code = self.generated_code

        # 检查是否同时过滤inTime和upTime
        if 'inTime' in code and 'upTime' not in code:
            issues.append("applist只过滤了inTime，需同时过滤upTime")
        elif 'upTime' in code and 'inTime' not in code:
            issues.append("applist只过滤了upTime，需同时过滤inTime")

        return len(issues) == 0, issues

    def review_with_llm(self) -> Dict:
        """使用LLM进行深度审核"""
        print("\n" + "=" * 70)
        print("3. LLM深度审核")
        print("=" * 70)

        prompt = f"""# 任务：审核特征工程代码

请审核以下Python代码的正确性：

## 审核要点

1. **语法合法性**：代码是否符合Python语法
2. **防穿越机制**：是否正确使用applyTime作为基准点
3. **动态类别**：是否从app_classification_cache动态提取类别
4. **FDC字段**：是否使用正确的字段名（3_hari, 7_hari, jumlahPlatformAktif）
5. **applist过滤**：是否同时过滤inTime和upTime
6. **安全除法**：是否有除0保护
7. **异常处理**：是否处理日期格式错误、缺失字段等
8. **代码规范**：是否有中文注释、函数是否独立

## 代码

```python
{self.generated_code}
```

## 输出格式

请输出JSON格式：

```json
{{
  "syntax_check": {{
    "passed": true/false,
    "errors": ["错误列表"]
  }},
  "logic_check": {{
    "passed": true/false,
    "issues": ["问题列表"]
  }},
  "suggestions": ["改进建议"],
  "overall_passed": true/false,
  "score": 0-100
}}
```

现在请审核：
"""

        messages = [{"role": "user", "content": prompt}]
        response = self.llm_client.chat(messages, temperature=0.1)

        # 提取JSON
        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                result = json.loads(json_str)
                print(f"   LLM审核完成")
                print(f"   总体通过: {result.get('overall_passed', False)}")
                print(f"   评分: {result.get('score', 0)}/100")
                return result
            else:
                print(f"   无法提取JSON")
                return {"error": "无法解析LLM响应"}
        except Exception as e:
            print(f"   JSON解析失败: {e}")
            return {"error": str(e)}

    def generate_report(self, syntax_result, logic_result, llm_result) -> str:
        """生成审核报告"""
        print("\n" + "=" * 70)
        print("4. 生成审核报告")
        print("=" * 70)

        report_file = 'outputs/feature_code/review_report.md'
        os.makedirs(os.path.dirname(report_file), exist_ok=True)

        lines = []
        lines.append("# 特征工程代码审核报告\n")

        # 语法检查
        lines.append("## 1. 语法合法性检查\n")
        if syntax_result[0]:
            lines.append("- ✅ **通过**")
        else:
            lines.append("- ❌ **未通过**")
            for error in syntax_result[1]:
                lines.append(f"  - {error}")

        lines.append("")

        # 逻辑检查
        lines.append("## 2. 逻辑正确性审核\n")
        if logic_result[0]:
            lines.append("- ✅ **通过**")
        else:
            lines.append(f"- ❌ **未通过** ({len(logic_result[1])}个问题)")
            for issue in logic_result[1]:
                lines.append(f"  - {issue}")

        lines.append("")

        # LLM审核
        lines.append("## 3. LLM深度审核\n")
        if 'error' not in llm_result:
            lines.append(f"- 总体通过: {'✅ 是' if llm_result.get('overall_passed') else '❌ 否'}")
            lines.append(f"- 评分: {llm_result.get('score', 0)}/100")
            if llm_result.get('suggestions'):
                lines.append(f"\n**改进建议**:")
                for suggestion in llm_result['suggestions']:
                    lines.append(f"- {suggestion}")
        else:
            lines.append(f"- LLM审核失败: {llm_result.get('error')}")

        lines.append("")

        # 总结
        lines.append("## 4. 总结\n")
        overall_passed = syntax_result[0] and logic_result[0] and llm_result.get('overall_passed', False)
        if overall_passed:
            lines.append("✅ **审核通过**：代码质量良好，可以进入下一阶段")
        else:
            lines.append("❌ **审核未通过**：需要修正以下问题后重新提交")
            lines.append("\n**需要修正的问题**:")
            if not syntax_result[0]:
                for error in syntax_result[1]:
                    lines.append(f"- {error}")
            if not logic_result[0]:
                for issue in logic_result[1]:
                    lines.append(f"- {issue}")

        lines.append("")

        report = '\n'.join(lines)
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"审核报告已保存: {report_file}")
        return report

    def save_review_result(self, syntax_result, logic_result, llm_result):
        """保存审核结果JSON"""
        result_file = 'outputs/feature_code/review_result.json'
        os.makedirs(os.path.dirname(result_file), exist_ok=True)

        result = {
            'syntax_check': {
                'passed': syntax_result[0],
                'errors': syntax_result[1]
            },
            'logic_check': {
                'passed': logic_result[0],
                'issues': logic_result[1]
            },
            'llm_review': llm_result,
            'overall_passed': syntax_result[0] and logic_result[0] and llm_result.get('overall_passed', False)
        }

        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"审核结果已保存: {result_file}")

    def run(self, auto_confirm: bool = False):
        """主执行流程

        Args:
            auto_confirm: 是否自动确认（无人工交互模式）
                - True: 自动通过，无需人工确认
                - False: 等待人工输入yes/no
        """
        print("=" * 70)
        print("特征审核Agent - 开始执行")
        if auto_confirm:
            print("⚠️  模式：自动确认（无人工交互）")
        print("=" * 70)

        # 1. 加载数据
        print("\n1. 加载数据...")
        self.load_feature_design()
        self.load_generated_code()

        # 2. 语法检查
        syntax_result = self.review_syntax()

        # 3. 逻辑检查
        logic_result = self.review_logic()

        # 4. LLM深度审核
        llm_result = self.review_with_llm()

        # 5. 生成报告
        report = self.generate_report(syntax_result, logic_result, llm_result)

        # 6. 保存结果
        self.save_review_result(syntax_result, logic_result, llm_result)

        # 7. Human-in-the-loop: 人工确认
        print("\n" + "=" * 70)
        print("7. 人工确认环节 (Human-in-the-Loop)")
        print("=" * 70)

        # 显示审核结果概要
        print("\n审核结果概要:")
        print(f"  - 语法检查: {'通过' if syntax_result[0] else '未通过'}")
        print(f"  - 逻辑检查: {'通过' if logic_result[0] else '未通过'}")
        if 'error' not in llm_result:
            print(f"  - LLM评分: {llm_result.get('score', 0)}/100")

        # 如果有问题，列出
        issues = syntax_result[1] + logic_result[1]
        if issues:
            print(f"\n⚠️ 发现 {len(issues)} 个问题:")
            for issue in issues:
                print(f"   - {issue}")

        # 人工确认提示
        print("\n" + "-" * 70)
        print("请查看审核报告: outputs/feature_code/review_report.md")
        print("-" * 70)

        overall_passed = syntax_result[0] and logic_result[0]

        if auto_confirm:
            # 自动模式：只要语法和逻辑通过就自动确认
            if overall_passed:
                print("\n✅ 自动确认：审核通过（auto_confirm=True）")
                final_result = True
            else:
                print("\n❌ 自动确认：审核未通过（语法或逻辑检查失败）")
                final_result = False
        else:
            # 交互模式：等待人工输入
            if overall_passed:
                user_confirm = input("\n语法和逻辑检查通过。是否确认审核通过? (yes/no): ").strip().lower()
                if user_confirm == 'yes':
                    print("\n✅ 人工确认：审核通过")
                    final_result = True
                else:
                    print("\n❌ 人工确认：审核不通过，需要修改代码")
                    final_result = False
            else:
                print("\n❌ 自动审核未通过，请修复问题后重新提交")
                print(f"   需要修复 {len(issues)} 个问题")
                final_result = False

        # 更新审核结果
        result_file = 'outputs/feature_code/review_result.json'
        if os.path.exists(result_file):
            with open(result_file, 'r', encoding='utf-8') as f:
                result_data = json.load(f)
            result_data['human_confirmed'] = final_result
            result_data['final_passed'] = final_result
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)

        # 8. 最终总结
        print("\n" + "=" * 70)
        print("特征审核Agent - 执行完成")
        print("=" * 70)

        if final_result:
            print(f"\n✅ **最终审核通过 (人工确认)**")
            if 'score' in llm_result:
                print(f"   LLM评分: {llm_result.get('score', 0)}/100")
        else:
            print(f"\n❌ **最终审核未通过**")
            if issues:
                print(f"   发现 {len(issues)} 个问题")
            print(f"   详见: outputs/feature_code/review_report.md")

        return final_result


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Feature Review Agent')
    parser.add_argument('--auto-confirm', action='store_true',
                        help='自动确认模式（无需人工输入）')
    args = parser.parse_args()

    agent = FeatureReviewAgent()
    agent.run(auto_confirm=args.auto_confirm)