"""
修复失败的LLM规则学习 - 针对religious和utility类别

这两个类别样本数过多（utility有3838个），导致prompt太长API超时。
解决方案：限制样本数为50个（足够学习规则特征）。
"""

import json
import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from utils.llm_client import LLMClient


def fix_failed_category(category: str, samples: list, output_file: str):
    """修复单个失败的类别"""

    print(f"\n⚙️  重新学习类别: {category} ({len(samples)} 个样本)")

    # 限制样本数为50个（避免prompt太长）
    max_samples = 50
    samples = samples[:max_samples]
    print(f"   使用样本数: {len(samples)} 个（限制为50个）")

    # 构建简化版Prompt
    prompt = f"""# 任务：从印尼APP样本中学习在线判定规则

## 背景
请分析以下**{category}**类别的APP包名，总结判定规则。

## 样本数据（共{len(samples)}个）

"""
    for i, sample in enumerate(samples, 1):
        pkg = sample['package_name']
        reason = sample.get('reason', '')
        prompt += f"{i}. `{pkg}`"
        if reason:
            prompt += f" - {reason}"
        prompt += "\n"

    prompt += f"""
## 输出要求

请输出JSON格式的规则（不要有其他文字）：

```json
{{
  "category": "{category}",
  "total_samples": {len(samples)},

  "keywords": {{
    "indonesian": ["印尼语特征词"],
    "english": ["英语特征词"],
    "description": "说明这些关键词为什么能区分{category}"
  }},

  "patterns": [
    {{
      "regex": "^正则表达式$",
      "description_cn": "详细的中文描述，说明这个正则匹配什么模式",
      "confidence": 0.9,
      "examples": ["示例1", "示例2"]
    }}
  ],

  "brands": [
    {{
      "name": "品牌名",
      "description": "品牌说明",
      "confidence": 0.95
    }}
  ],

  "exclusion_rules": [
    {{
      "rule": "如果包含xxx词，则不属于{category}",
      "reason": "说明为什么"
    }}
  ],

  "reasoning": "综合推理逻辑：为什么上述规则能准确判定{category}类别"
}}
```

## 重要要求

1. **正则表达式**：必须合法，不能用[WORD]等占位符
2. **中文描述**：每个正则必须有description_cn字段
3. **区分度**：关键词必须是该类别独有，不要与其他类别冲突

请输出规则JSON：
"""

    # 调用LLM
    llm_client = LLMClient()
    max_retries = 3

    for attempt in range(max_retries):
        try:
            messages = [{"role": "user", "content": prompt}]
            response = llm_client.chat(messages, temperature=0)

            # 提取JSON
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()

            rules = json.loads(json_str)
            print(f"✅ {category} 规则学习完成")
            print(f"   - 关键词: {len(rules.get('keywords', {}).get('indonesian', []) + rules.get('keywords', {}).get('english', []))} 个")
            print(f"   - 正则模式: {len(rules.get('patterns', []))} 个")
            print(f"   - 品牌: {len(rules.get('brands', []))} 个")

            return {category: rules}

        except Exception as e:
            print(f"   ⚠️  尝试 {attempt + 1}/{max_retries} 失败: {e}")
            if attempt < max_retries - 1:
                import time
                time.sleep(5)

    # 全部失败，返回错误
    return {category: {"error": f"LLM调用失败，已重试{max_retries}次: {str(e)}"}}


def main():
    """主函数"""

    print("=" * 60)
    print("修复失败的LLM规则学习")
    print("=" * 60)

    # 加载数据
    cache_file = 'outputs/app_analysis/classification_complete_11850.json'
    with open(cache_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    classifications = data['classifications']

    # 提取religious和utility类别的样本
    categories = {'religious': [], 'utility': []}

    for pkg_name, info in classifications.items():
        category = info['category']
        if category in categories:
            categories[category].append({
                'package_name': pkg_name,
                'reason': info.get('reason', '')
            })

    print(f"\n📊 样本统计:")
    for cat, samples in categories.items():
        print(f"   - {cat}: {len(samples)} 个样本")

    # 修复每个失败的类别
    all_fixed_rules = {}

    for category, samples in categories.items():
        fixed_rules = fix_failed_category(category, samples, None)
        all_fixed_rules.update(fixed_rules)

    # 加载现有规则库
    rules_file = 'outputs/risk_rules/online_app_classification_rules_llm.json'
    with open(rules_file, 'r', encoding='utf-8') as f:
        existing_rules = json.load(f)

    # 更新修复的规则
    existing_rules['rules'].update(all_fixed_rules)

    # 保存更新后的规则
    with open(rules_file, 'w', encoding='utf-8') as f:
        json.dump(existing_rules, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 规则库已更新: {rules_file}")
    print(f"📊 总规则数: {len(existing_rules['rules'])} 个类别")

    # 检查是否还有错误
    failed_categories = [cat for cat, rules in existing_rules['rules'].items() if 'error' in rules]
    if failed_categories:
        print(f"⚠️  仍有失败的类别: {failed_categories}")
    else:
        print("✅ 所有类别规则学习成功！")

    # 生成摘要
    summary_file = 'outputs/risk_rules/online_app_classification_rules_llm_summary.md'
    generate_summary(existing_rules, summary_file)


def generate_summary(rules_data: dict, output_file: str):
    """生成规则摘要Markdown"""

    lines = []
    lines.append("# LLM生成的在线APP分类规则库（修复版）\n")
    lines.append(f"生成时间: {rules_data['meta']['learning_date']}")
    lines.append(f"学习方法: {rules_data['meta']['learning_method']}")
    lines.append(f"修复说明: 针对utility和religious类别重新学习（限制50个样本）\n")
    lines.append("---\n")

    for category, rules in sorted(rules_data['rules'].items(), key=lambda x: x[1].get('total_samples', 0), reverse=True):
        if 'error' in rules:
            lines.append(f"## {category} ❌")
            lines.append(f"- **错误**: {rules['error']}\n")
            lines.append("---\n")
            continue

        lines.append(f"## {category}")
        lines.append(f"- 样本数: {rules.get('total_samples', 'N/A')}")

        # 关键词
        keywords = rules.get('keywords', {})
        all_keywords = keywords.get('indonesian', []) + keywords.get('english', [])
        if all_keywords:
            lines.append(f"- 关键词: {', '.join(all_keywords[:20])}")

        # 正则模式
        patterns = rules.get('patterns', [])
        if patterns:
            pattern_strs = [p.get('regex', '') for p in patterns[:5]]
            lines.append(f"- 正则模式: {', '.join(pattern_strs[:5])}")

        # 品牌
        brands = rules.get('brands', [])
        if brands:
            brand_names = [b.get('name', '') for b in brands[:10]]
            lines.append(f"- 品牌: {', '.join(brand_names[:10])}")

        # 推理逻辑
        if 'reasoning' in rules:
            lines.append(f"\n**推理逻辑**: {rules['reasoning'][:200]}...\n")

        lines.append("")
        lines.append("---\n")

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"📝 摘要已更新: {output_file}")


if __name__ == '__main__':
    main()
