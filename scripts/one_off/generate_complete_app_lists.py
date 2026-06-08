"""
生成完整的好/坏客户应用清单（全部数据），并添加LLM分类
"""

import pandas as pd
import json

# 1. 读取完整的应用分析数据
with open('outputs/app_analysis/app_analysis_summary.json', 'r', encoding='utf-8') as f:
    summary = json.load(f)

print(f"总样本: {summary['total_samples']}")
print(f"好客户: {summary['good_customers']}")
print(f"坏客户: {summary['bad_customers']}")

# 2. 读取LLM分类结果
with open('outputs/app_analysis/app_classification_result.json', 'r', encoding='utf-8') as f:
    classification = json.load(f)

classifications = classification.get('classifications', {})

# 3. 读取原始分析数据（需要重新处理原始JSON数据）
# 由于summary只包含统计信息，我们需要重新加载原始JSON
print("\n需要重新处理原始数据以获取完整应用列表...")

# 实际上，summary中的数据已经是全量的，但只保存了top应用
# 我们需要从CSV文件中读取完整数据
# 当前CSV文件包含的实际上是完整数据（从analyze_all_apps.py直接输出）

# 检查good_only_apps.csv是否包含完整数据
good_only_df = pd.read_csv('outputs/app_analysis/good_only_apps.csv')
bad_only_df = pd.read_csv('outputs/app_analysis/high_risk_apps.csv')
common_df = pd.read_csv('outputs/app_analysis/common_apps.csv')

print(f"\ngood_only_apps.csv: {len(good_only_df)} 行")
print(f"high_risk_apps.csv: {len(bad_only_df)} 行")
print(f"common_apps.csv: {len(common_df)} 行")

# 如果这些文件包含完整数据（2147个好客户、6892个坏客户），就直接使用
# 否则需要重新处理

# 保存完整清单并添加分类
def add_classification(app_name):
    """添加LLM分类"""
    if app_name in classifications:
        return classifications[app_name].get('category', 'unknown')
    return 'unclassified'

def add_confidence(app_name):
    """添加置信度"""
    if app_name in classifications:
        return classifications[app_name].get('confidence', 'N/A')
    return 'N/A'

# 保存好客户完整清单
good_only_df['category'] = good_only_df['app'].apply(add_classification)
good_only_df['llm_confidence'] = good_only_df['app'].apply(add_confidence)
good_only_df.to_csv('outputs/app_analysis/good_customer_apps_complete.csv', index=False)

print(f"\n✓ 好客户完整应用清单: {len(good_only_df)} 个")
print(f"  已分类: {(good_only_df['category'] != 'unclassified').sum()} 个")
print(f"  未分类: {(good_only_df['category'] == 'unclassified').sum()} 个")
print(f"  文件: outputs/app_analysis/good_customer_apps_complete.csv")

# 保存坏客户完整清单
bad_only_df['category'] = bad_only_df['app'].apply(add_classification)
bad_only_df['llm_confidence'] = bad_only_df['app'].apply(add_confidence)
bad_only_df.to_csv('outputs/app_analysis/bad_customer_apps_complete.csv', index=False)

print(f"\n✓ 坏客户完整应用清单: {len(bad_only_df)} 个")
print(f"  已分类: {(bad_only_df['category'] != 'unclassified').sum()} 个")
print(f"  未分类: {(bad_only_df['category'] == 'unclassified').sum()} 个")
print(f"  文件: outputs/app_analysis/bad_customer_apps_complete.csv")

# 保存共有应用完整清单
common_df['category'] = common_df['app'].apply(add_classification)
common_df['llm_confidence'] = common_df['app'].apply(add_confidence)
common_df.to_csv('outputs/app_analysis/common_apps_complete.csv', index=False)

print(f"\n✓ 共有应用完整清单: {len(common_df)} 个")
print(f"  已分类: {(common_df['category'] != 'unclassified').sum()} 个")
print(f"  未分类: {(common_df['category'] == 'unclassified').sum()} 个")
print(f"  文件: outputs/app_analysis/common_apps_complete.csv")

# 4. 按类别统计
print("\n" + "="*80)
print("应用分类统计")
print("="*80)

from collections import Counter, defaultdict

# 合并所有应用
all_apps = pd.concat([
    good_only_df[['app', 'category']].assign(source='good_only'),
    bad_only_df[['app', 'category']].assign(source='bad_only'),
    common_df[['app', 'category']].assign(source='common')
], ignore_index=True)

# 按类别统计
category_stats = defaultdict(lambda: {'good': 0, 'bad': 0, 'common': 0, 'total': 0})

for _, row in all_apps.iterrows():
    cat = row['category']
    source = row['source']
    category_stats[cat][source] += 1
    category_stats[cat]['total'] += 1

print(f"\n{'类别':<30} {'好客户':>8} {'坏客户':>8} {'共有':>8} {'总计':>8}")
print("-" * 70)
for cat in sorted(category_stats.keys(), key=lambda x: category_stats[x]['total'], reverse=True):
    stats = category_stats[cat]
    print(f"{cat:<30} {stats['good']:>8} {stats['bad']:>8} {stats['common']:>8} {stats['total']:>8}")
