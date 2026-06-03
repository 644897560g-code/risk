"""
测试LLM规则学习 - 先对gambling类别进行测试
"""

import json
import sys
sys.path.append('/Users/apple/Desktop/agents/risk-agent-cc-indo')

from data.rule_learner_llm import LLMRuleLearner

# 创建学习器
learner = LLMRuleLearner(
    classified_file='outputs/app_analysis/classification_complete_11850.json'
)

# 加载数据
learner.load_data()

# 提取gambling类别的所有样本
classifications = learner.data['classifications']
gambling_samples = []

for pkg_name, info in classifications.items():
    if info['category'] == 'gambling':
        gambling_samples.append({
            'package_name': pkg_name,
            'category': info['category'],
            'confidence': info['confidence'],
            'reason': info.get('reason', '')
        })

print(f"📊 gambling类别共有 {len(gambling_samples)} 个样本")
print(f"\n前10个样本:")
for sample in gambling_samples[:10]:
    print(f"  - {sample['package_name']}: {sample['reason']}")

# 调用LLM学习规则
print(f"\n⚙️  开始LLM规则学习（使用全部 {len(gambling_samples)} 个样本）...")
rules = learner.learn_category_rules('gambling', gambling_samples)

# 保存结果
output_file = 'outputs/risk_rules/test_gambling_rules_llm.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(rules, f, ensure_ascii=False, indent=2)

print(f"\n✅ 测试完成！gambling规则已保存到: {output_file}")
print(f"\n规则摘要:")
print(f"  - 关键词数: {len(rules.get('keywords', {}).get('indonesian', [])) + len(rules.get('keywords', {}).get('english', []))}")
print(f"  - 正则模式数: {len(rules.get('patterns', []))}")
print(f"  - 品牌数: {len(rules.get('brands', []))}")

# 打印前3个正则模式
if 'patterns' in rules:
    print(f"\n前3个正则模式:")
    for i, pattern in enumerate(rules['patterns'][:3], 1):
        print(f"  {i}. {pattern['regex']}")
        print(f"     描述: {pattern.get('description_cn', 'N/A')}")
        print(f"     置信度: {pattern.get('confidence', 0)}")
