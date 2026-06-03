"""
修复失败的LLM规则学习 - 针对religious和utility类别

使用全部样本（不限制数量）重新调用LLM。
"""

import json
import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from utils.llm_client import LLMClient


def fix_failed_category(category: str, samples: list):
    """修复单个失败的类别 - 使用全部样本"""

    print(f"\n⚙️  重新学习类别: {category}（使用全部 {len(samples)} 个样本）")

    # 使用全部样本构建prompt
    prompt = f"""# 任务：从印尼APP样本中学习在线判定规则

## 背景
请分析以下**{category}**类别的APP包名，总结判定规则。

## 样本数据（共{len(samples)}个）

"""
    for i, sample in enumerate(samples, 1):
        # 每个样本：包名 + 说明（如果有）
        pkg = sample['package_name']
        reason = sample.get('reason', '')
        prompt += f"{i}. `{pkg}`"
        if reason:
            prompt += f" - {reason}"
        prompt += "\n"

    prompt += f"""
## 输出要求

请输出JSON格式的规则：

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
      "regex": "^合法正则表达式$",
      "description_cn": "详细的中文描述",
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

  "reasoning": "综合推理逻辑"
}}
```

## 重要要求

1. **正则表达式**必须合法，不能用[WORD]等占位符
2. **中文描述**每个正则必须有description_cn字段
3. **高区分度**关键词，不要与其他类别冲突

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
            else:
                # 查找{和}
                start = response.find('{')
                end = response.rfind('}')
                if start != -1 and end != -1:
                    json_str = response[start:end+1]

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
                time.sleep(10)  # 等待10秒再重试

    return {category: {"error": f"LLM调用失败，已重试{max_retries}次: {str(e)}"}}


def main():
    """主函数"""

    print("=" * 60)
    print("修复失败的LLM规则学习（全量样本版）")
    print("=" * 60)

    # 加载数据
    cache_file = 'outputs/app_analysis/classification_complete_11850.json'
    with open(cache_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    classifications = data['classifications']

    # 提取religious和utility类别的样本
    religious_samples = []
    utility_samples = []

    for pkg_name, info in classifications.items():
        if info['category'] == 'religious':
            religious_samples.append({
                'package_name': pkg_name,
                'reason': info.get('reason', '')
            })
        elif info['category'] == 'utility':
            utility_samples.append({
                'package_name': pkg_name,
                'reason': info.get('reason', '')
            })

    print(f"\n📊 样本统计:")
    print(f"   - religious: {len(religious_samples)} 个样本")
    print(f"   - utility: {len(utility_samples)} 个样本")

    # 修复每个失败的类别
    failed = False
    fixed_rules = {}

    for category, samples in [('religious', religious_samples), ('utility', utility_samples)]:
        result = fix_failed_category(category, samples)
        if 'error' in result[category]:
            print(f"❌ {category} 最终失败: {result[category]['error']}")
            failed = True
        else:
            fixed_rules.update(result)

    if failed:
        print("\n⚠️  仍有类别失败，请检查API连接或样本质量")
        return

    # 加载现有规则库
    rules_file = 'outputs/risk_rules/online_app_classification_rules_llm.json'
    with open(rules_file, 'r', encoding='utf-8') as f:
        existing_rules = json.load(f)

    # 更新修复的规则
    existing_rules['rules'].update(fixed_rules)

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


if __name__ == '__main__':
    main()
