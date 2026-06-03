"""
LLM规则学习器 - 使用qwen3.6-plus从已分类样本中学习高质量判定规则

优势：
1. 深度语义理解，不止词频统计
2. 能识别复杂模式（如白牌模板）
3. 能生成可解释的推理逻辑
4. 能处理易混淆场景
5. 能生成精确的正则表达式
"""

import json
import os
import sys
# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from utils.llm_client import LLMClient


class LLMRuleLearner:
    """使用LLM进行规则学习"""

    def __init__(self, classified_file: str):
        """
        Args:
            classified_file: 已分类APP的JSON文件路径
        """
        self.classified_file = classified_file
        self.data = None
        self.llm_client = LLMClient()  # 使用默认配置（qwen3.6-plus）
        self.rules = {}

    def load_data(self):
        """加载已分类数据"""
        with open(self.classified_file, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        print(f"✅ 加载了 {self.data['total_apps']} 个已分类APP")

    def _build_category_prompt(self, category: str, samples: list) -> str:
        """
        构建类别规则学习Prompt

        Args:
            category: 类别名称
            samples: 该类别下的样本列表

        Returns:
            Prompt文本
        """
        # 提取样本信息（使用全部样本）
        package_names = [s['package_name'] for s in samples]
        reasons = [s.get('reason', '') for s in samples]

        # 构建Prompt（使用全部样本）
        prompt = f"""# 任务：从印尼APP样本中学习在线判定规则

## 背景
你正在分析印尼智能手机用户安装的应用程序包名（package names），需要从中识别出**{category}**类别的应用。

## 已知信息
- 这些应用都属于**{category}**类别
- 总样本数：{len(samples)}个（**使用全部样本**，非采样）
- 应用包名和说明如下（共{len(samples)}个）：

"""
        # 列出所有样本（最多200个避免token超限）
        max_samples = min(200, len(samples))
        for i, (pkg, reason) in enumerate(zip(package_names[:max_samples], reasons[:max_samples]), 1):
            prompt += f"{i}. 包名: `{pkg}`"
            if reason:
                prompt += f"\n   说明: {reason}"
            prompt += "\n"

        prompt += f"""
## 你的任务

请从这些样本中总结出**在线判定规则**，使得系统能够实时判断一个新APP是否属于**{category}**类别。

## 输出要求

请输出JSON格式的规则（不要有其他文字）：

```json
{{
  "category": "{category}",
  "total_samples": {len(samples)},

  "keywords": {{
    "indonesian": ["关键词1", "关键词2", ...],
    "english": ["关键词1", "关键词2", ...],
    "description": "说明这些关键词为什么能区分{category}"
  }},

  "patterns": [
    {{
      "regex": "^正则表达式1$",
      "description_cn": "详细的中文描述，说明这个正则表达式匹配什么模式、为什么能识别{category}",
      "confidence": 0.9,
      "examples": ["匹配的包名示例1", "匹配的包名示例2"]
    }},
    ...
  ],

  "brands": [
    {{
      "name": "品牌名1",
      "description": "品牌说明",
      "confidence": 0.95
    }},
    ...
  ],

  "exclusion_rules": [
    {{
      "rule": "如果包含xxx词，则不属于{category}",
      "reason": "说明为什么"
    }},
    ...
  ],

  "confusion_risk": [
    {{
      "confused_with": "可能混淆的其他类别",
      "distinguishing_feature": "如何区分"
    }},
    ...
  ],

  "reasoning": "综合推理逻辑：为什么上述规则能准确判定{category}类别"
}}
```

## 重要指导原则

1. **正则表达式要求**（非常重要！）：
   - 必须是**合法的正则语法**（如 `^com\\.id\\d+\\..*` 或 `.*slot.*\\d+.*`）
   - 不能使用 `[WORD]`、`[NUM]`、`[SHORT]` 等抽象占位符（这些不是合法正则！）
   - 要精确到包名级别（如 `^com\\.higgs\\..*` 或 `^com\\.id5dan777\\..*`）
   - **每个正则必须配中文描述**（`description_cn`字段），说明这个正则是匹配什么模式

2. **关键词要求**：
   - 必须是**高区分度**的词（在{category}中常见，其他类别少见）
   - 不能有冲突词（如"game"在所有类别都有，不要用）
   - 优先选择印尼语特征词（如"judi", "pinjaman", "slot"）

3. **排除规则**：
   - 明确什么情况下**不应该**判定为{category}
   - 例如：如果包含"bank"，可能是banking而非fintech_lending

4. **置信度评估**：
   - 0.9-1.0: 几乎100%准确（如已知品牌）
   - 0.8-0.9: 高度可信（如明确关键词+模式）
   - 0.7-0.8: 较可信（如单一关键词）
   - <0.7: 需要人工审核

5. **易混淆处理**：
   - 说明可能与其他哪些类别混淆
   - 给出区分方法

## 开始

请分析上述样本，输出规则JSON：
"""
        return prompt

    def _high_risk_category_prompt(self, category: str, samples: list,
                                   common_samples: dict) -> str:
        """
        高风险类别增强Prompt（包含对比样本）

        Args:
            category: 类别名称
            samples: 该类别样本
            common_samples: 其他类别中容易混淆的样本

        Returns:
            增强Prompt
        """
        base_prompt = self._build_category_prompt(category, samples)

        # 添加对比样本
        confusion_section = """
## 对比样本（易混淆的误判案例）

以下是**容易被误判为{category}**，但实际属于其他类别的应用：

""".format(category=category)

        for confused_cat, confused_pkgs in list(common_samples.items())[:3]:
            confusion_section += f"\n### 实际属于 {confused_cat}:\n"
            for pkg in confused_pkgs[:5]:
                confusion_section += f"- `{pkg['package_name']}`: {pkg.get('reason', '')}\n"

        confusion_section += """
请在总结规则时，特别注意与这些误判案例的区分。
"""

        return base_prompt + confusion_section

    def learn_category_rules(self, category: str, samples: list) -> dict:
        """
        学习单个类别的规则

        Args:
            category: 类别名称
            samples: 该类别的样本列表

        Returns:
            规则字典
        """
        print(f"\n⚙️  学习类别: {category} ({len(samples)} 个样本)")

        # 高风险类别需要增强Prompt
        high_risk_categories = [
            'gambling', 'cash_loan', 'fintech_lending',
            'fake_gps', 'clone_app', 'app_store'
        ]

        if category in high_risk_categories:
            # TODO: 可以添加对比样本
            prompt = self._build_category_prompt(category, samples)
        else:
            prompt = self._build_category_prompt(category, samples)

        try:
            # 构建messages
            messages = [
                {"role": "user", "content": prompt}
            ]

            # 调用LLM
            response = self.llm_client.chat(
                messages=messages,
                temperature=0  # 规则学习需要确定性输出
            )

            # 提取JSON（LLM可能返回markdown代码块）
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()

            rules = json.loads(json_str)

            # 验证正则表达式是否合法
            import re as regex_module
            invalid_patterns = []
            for pattern in rules.get('patterns', []):
                try:
                    regex_module.compile(pattern['regex'])
                except regex_module.error as e:
                    invalid_patterns.append({
                        "pattern": pattern['regex'],
                        "error": str(e)
                    })
                    # 标记为无效
                    pattern['regex'] = "INVALID_" + pattern['regex']
                    pattern['validation_error'] = str(e)

            if invalid_patterns:
                print(f"⚠️  {category} 发现 {len(invalid_patterns)} 个无效正则表达式:")
                for ip in invalid_patterns:
                    print(f"   - {ip['pattern']}: {ip['error']}")

            print(f"✅ {category} 规则学习完成")
            print(f"   - 关键词: {len(rules['keywords']['indonesian']) + len(rules['keywords']['english'])} 个")
            print(f"   - 正则模式: {len(rules['patterns'])} 个")
            print(f"   - 品牌: {len(rules['brands'])} 个")

            return rules

        except Exception as e:
            print(f"❌ {category} 规则学习失败: {e}")
            # 返回空规则结构
            return {
                "category": category,
                "total_samples": len(samples),
                "keywords": {},
                "patterns": [],
                "brands": [],
                "exclusion_rules": [],
                "error": str(e)
            }

    def learn_all_rules(self):
        """学习所有类别的规则"""
        if not self.data:
            self.load_data()

        classifications = self.data['classifications']

        # 按类别分组
        categories = {}
        for pkg_name, info in classifications.items():
            category = info['category']
            if category not in categories:
                categories[category] = []
            categories[category].append({
                'package_name': pkg_name,
                'category': category,
                'confidence': info['confidence'],
                'reason': info.get('reason', '')
            })

        print(f"\n📊 共 {len(categories)} 个类别")

        # 对每个类别学习规则（排除other类别）
        for category, apps in categories.items():
            # 跳过other类别（兜底类别，不需要规则）
            if category == 'other':
                print(f"⏭️  跳过类别: {category}（兜底类别）")
                continue

            # 使用全部样本（不采样）
            samples = apps
            print(f"\n⏳ 学习类别: {category}（使用全部 {len(samples)} 个样本）")

            rules = self.learn_category_rules(category, samples)
            self.rules[category] = rules

        print(f"\n✅ 所有类别规则学习完成！共 {len(self.rules)} 个类别")

        return self.rules

    def save_rules(self, output_file: str):
        """保存规则到JSON文件"""
        if not self.rules:
            raise ValueError("规则尚未学习，请先调用 learn_all_rules()")

        output = {
            "meta": {
                "total_apps": self.data['total_apps'],
                "total_categories": len(self.rules),
                "excluded_categories": ["other"],
                "learning_date": "2026-04-26",
                "learning_method": "LLM_rule_learning_qwen3.6-plus",
                "sample_policy": "使用全部样本（不采样）",
                "pattern_description": "正则模式包含中文描述（description_cn字段）"
            },
            "high_risk_categories": [
                'gambling', 'cash_loan', 'fintech_lending',
                'fake_gps', 'clone_app', 'app_store'
            ],
            "rules": self.rules
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"\n💾 规则已保存到: {output_file}")

    def generate_summary_md(self, output_file: str):
        """生成规则摘要Markdown"""
        if not self.rules:
            raise ValueError("规则尚未学习，请先调用 learn_all_rules()")

        lines = []
        lines.append("# LLM生成的在线APP分类规则库\n")
        lines.append(f"生成时间: 2026-04-26\n")
        lines.append(f"学习方法: qwen3.6-plus LLM规则学习\n")
        lines.append(f"每类别样本数: 50\n")
        lines.append("---\n")

        for category, rules in sorted(self.rules.items(),
                                     key=lambda x: x[1].get('total_samples', 0),
                                     reverse=True):
            lines.append(f"## {category}\n")
            lines.append(f"- 样本数: {rules.get('total_samples', 'N/A')}")

            # 关键词
            keywords = rules.get('keywords', {})
            all_keywords = (
                keywords.get('indonesian', []) +
                keywords.get('english', [])
            )
            if all_keywords:
                lines.append(f"- 关键词模式: {', '.join(all_keywords[:20])}")

            # 正则模式
            patterns = rules.get('patterns', [])
            if patterns:
                pattern_strs = [p.get('regex', '') for p in patterns[:5]]
                lines.append(f"- 正则模式: {', '.join(pattern_strs[:5])}")

            # 品牌
            brands = rules.get('brands', [])
            if brands:
                brand_names = [b.get('name', '') for b in brands[:10]]
                lines.append(f"- 品牌模式: {', '.join(brand_names[:10])}")

            # 推理说明
            if 'reasoning' in rules:
                lines.append(f"\n**推理逻辑**: {rules['reasoning']}\n")

            lines.append("")
            lines.append("---\n")

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        print(f"📝 规则摘要已保存到: {output_file}")


if __name__ == '__main__':
    # 使用示例
    learner = LLMRuleLearner(
        classified_file='outputs/app_analysis/classification_complete_11850.json'
    )

    # 学习规则（使用全部样本，排除other类别）
    learner.load_data()
    learner.learn_all_rules()

    # 保存规则
    output_json = 'outputs/risk_rules/online_app_classification_rules_llm.json'
    output_md = 'outputs/risk_rules/online_app_classification_rules_llm_summary.md'
    learner.save_rules(output_json)
    learner.generate_summary_md(output_md)

    print("\n🎉 规则学习完成！")
    print(f"📁 输出文件:")
    print(f"   - JSON规则: {output_json}")
    print(f"   - Markdown摘要: {output_md}")
