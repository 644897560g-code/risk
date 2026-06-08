"""
统计分析：好坏客户的applist分布对比
"""

import sys
import os
import json
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))

from data.data_loader import DataLoader, ShortLinkFetcher

# 加载数据
loader = DataLoader()
short_links = loader.load_short_links()
model_samples = loader.load_model_samples()

print("="*80)
print("数据统计分析")
print("="*80)

# 分离好坏客户
good_customers = model_samples[model_samples['is_overdue'] == 0]
bad_customers = model_samples[model_samples['is_overdue'] == 1]

print(f"\n总样本: {len(model_samples)}")
print(f"好客户 (is_overdue=0): {len(good_customers)}")
print(f"坏客户 (is_overdue=1): {len(bad_customers)}")

# 构建好坏客户的orderId集合
good_order_ids = set(good_customers['source_order_no'].tolist())
bad_order_ids = set(bad_customers['source_order_no'].tolist())

print(f"\n好客户订单ID数: {len(good_order_ids)}")
print(f"坏客户订单ID数: {len(bad_order_ids)}")

# 采样分析（先分析前100条看看）
sample_size = 100
fetcher = ShortLinkFetcher()
sample_links = short_links[:sample_size]

print(f"\n开始从{sample_size}条短链中抽取applist...")

# 分别收集好坏客户的app
good_apps = []
bad_apps = []

json_data_list = fetcher.fetch_batch(sample_links)

for data in json_data_list:
    order_id = data.get('orderId', '')
    app_list = data.get('params', {}).get('appList', [])

    packages = [app.get('packageX', '') for app in app_list if app.get('packageX')]

    if order_id in good_order_ids:
        good_apps.extend(packages)
    elif order_id in bad_order_ids:
        bad_apps.extend(packages)

print(f"\n好客户应用安装记录: {len(good_apps)}")
print(f"坏客户应用安装记录: {len(bad_apps)}")

# 去重统计
good_apps_unique = set(good_apps)
bad_apps_unique = set(bad_apps)

print(f"\n好客户独立应用数: {len(good_apps_unique)}")
print(f"坏客户独立应用数: {len(bad_apps_unique)}")

# 交集
common_apps = good_apps_unique & bad_apps_unique
print(f"好坏客户共有应用数: {len(common_apps)}")

# 独有应用
good_only = good_apps_unique - bad_apps_unique
bad_only = bad_apps_unique - good_apps_unique
print(f"好客户独有应用: {len(good_only)}")
print(f"坏客户独有应用: {len(bad_only)}")

# Top 50高频应用对比
from collections import Counter

good_app_counts = Counter(good_apps)
bad_app_counts = Counter(bad_apps)

print("\n" + "="*80)
print("好客户 Top 30 高频应用:")
print("="*80)
for app, count in good_app_counts.most_common(30):
    pct = count / len(good_apps) * 100
    bad_count = bad_app_counts.get(app, 0)
    bad_pct = bad_count / len(bad_apps) * 100 if bad_count > 0 else 0
    print(f"  {app:60s} 好:{count:3d} ({pct:4.1f}%)  坏:{bad_count:3d} ({bad_pct:4.1f}%)")

print("\n" + "="*80)
print("坏客户 Top 30 高频应用:")
print("="*80)
for app, count in bad_app_counts.most_common(30):
    pct = count / len(bad_apps) * 100
    good_count = good_app_counts.get(app, 0)
    good_pct = good_count / len(good_apps) * 100 if good_count > 0 else 0
    print(f"  {app:60s} 坏:{count:3d} ({pct:4.1f}%)  好:{good_count:3d} ({good_pct:4.1f}%)")

# 计算每个应用的"坏客户倾向度"
print("\n" + "="*80)
print("坏客户倾向度最高的应用（坏客户安装率 / 好客户安装率）:")
print("="*80)

app_risk_ratio = {}
for app in good_apps_unique | bad_apps_unique:
    good_count = good_app_counts.get(app, 0)
    bad_count = bad_app_counts.get(app, 0)

    good_rate = good_count / len(good_apps) if len(good_apps) > 0 else 0
    bad_rate = bad_count / len(bad_apps) if len(bad_apps) > 0 else 0

    if good_rate > 0:
        ratio = bad_rate / good_rate
    else:
        ratio = float('inf') if bad_rate > 0 else 0

    # 只考虑安装次数>=3的应用
    if good_count + bad_count >= 3:
        app_risk_ratio[app] = {
            'ratio': ratio,
            'good_count': good_count,
            'bad_count': bad_count,
            'good_rate': good_rate,
            'bad_rate': bad_rate
        }

# 按风险比率排序
sorted_apps = sorted(app_risk_ratio.items(), key=lambda x: x[1]['ratio'], reverse=True)

for i, (app, stats) in enumerate(sorted_apps[:30]):
    print(f"  {i+1:2d}. {app:55s} 比率:{stats['ratio']:6.1f}x  好:{stats['good_count']:3d}  坏:{stats['bad_count']:3d}")

print("\n" + "="*80)
print("总结建议:")
print("="*80)
print(f"1. 去重后总应用数: {len(good_apps_unique | bad_apps_unique)}")
print(f"2. 好客户独有应用: {len(good_only)} （可能包含更多保守型应用）")
print(f"3. 坏客户独有应用: {len(bad_only)} （可能包含高风险借贷应用）")
print(f"4. 共有应用: {len(common_apps)} （需要看安装频次差异）")
print(f"\n5. 建议LLM分析策略:")
print(f"   - 好客户独立应用列表: {len(good_apps_unique)}个")
print(f"   - 坏客户独立应用列表: {len(bad_apps_unique)}个")
print(f"   - 分别让LLM分析这两类应用的特征差异")
