"""
从2272个有标签样本提取完整应用清单

只处理有好坏标签的2272个样本（626个好客户 + 1646个坏客户）
"""

import sys
import os
import json
import pandas as pd
from collections import defaultdict
import time

sys.path.insert(0, os.path.dirname(__file__))

from data.data_loader import DataLoader, ShortLinkFetcher

def main():
    print("="*80)
    print("从2272个有标签样本提取完整应用清单")
    print("="*80)

    # 1. 加载数据
    print("\n步骤1: 加载数据...")
    loader = DataLoader()
    fetcher = ShortLinkFetcher()

    short_links = loader.load_short_links()
    model_samples = loader.load_model_samples()

    print(f"   短链总数: {len(short_links)}")
    print(f"   建模样本: {len(model_samples)}")

    # 2. 只保留有标签样本对应的短链
    # 建模样本中的source_order_no对应短链中的订单ID
    model_order_ids = set(model_samples['source_order_no'].tolist())
    print(f"   有标签订单数: {len(model_order_ids)}")

    # 分离好坏客户
    good_customers = model_samples[model_samples['is_overdue'] == 0]
    bad_customers = model_samples[model_samples['is_overdue'] == 1]

    good_order_ids = set(good_customers['source_order_no'].tolist())
    bad_order_ids = set(bad_customers['source_order_no'].tolist())

    print(f"   好客户: {len(good_order_ids)}")
    print(f"   坏客户: {len(bad_order_ids)}")

    # 3. 过滤只处理有标签的样本
    print(f"\n步骤2: 过滤出{len(model_order_ids)}个有标签样本的短链...")

    # 需要找出哪些短链对应的订单ID在建模样本中
    # 由于短链和订单ID的对应关系需要通过网络请求获取，我们先采样检查
    print(f"   开始检查哪些短链属于建模样本...")

    # 创建订单ID -> 短链的映射（通过遍历所有短链）
    order_to_link = {}
    for i, link in enumerate(short_links):
        try:
            data = fetcher.fetch_json(link)
            if data:
                order_id = data.get('orderId', '')
                if order_id in model_order_ids:
                    order_to_link[order_id] = link
        except:
            pass

        if (i + 1) % 100 == 0:
            print(f"   已检查: {i+1}/{len(short_links)}")

    print(f"\n   找到{len(order_to_link)}个建模样本对应的短链")

    # 4. 处理有标签样本的应用数据
    print(f"\n步骤3: 处理{len(order_to_link)}个有标签样本的应用数据...")

    good_apps = defaultdict(int)
    bad_apps = defaultdict(int)
    success_count = 0
    fail_count = 0

    for i, (order_id, link) in enumerate(order_to_link.items()):
        try:
            data = fetcher.fetch_json(link)
            if not data:
                fail_count += 1
                continue

            success_count += 1
            app_list = data.get('params', {}).get('appList', [])

            for app in app_list:
                package = app.get('packageX', '')
                if not package:
                    continue

                if order_id in good_order_ids:
                    good_apps[package] += 1
                elif order_id in bad_order_ids:
                    bad_apps[package] += 1

        except Exception as e:
            fail_count += 1

        # 进度更新
        if (i + 1) % 50 == 0:
            print(f"   进度: {i+1}/{len(order_to_link)} - "
                  f"成功: {success_count}, 失败: {fail_count}")

    print(f"\n   最终: 成功={success_count}, 失败={fail_count}")

    # 5. 计算去重应用
    print(f"\n步骤4: 计算去重应用...")

    good_only = {k: v for k, v in good_apps.items() if k not in bad_apps}
    bad_only = {k: v for k, v in bad_apps.items() if k not in good_apps}
    common = {k: v for k, v in good_apps.items() if k in bad_apps}

    print(f"   好客户独有应用: {len(good_only)}")
    print(f"   坏客户独有应用: {len(bad_only)}")
    print(f"   共有应用: {len(common)}")
    print(f"   总独立应用: {len(good_only) + len(bad_only) + len(common)}")

    # 6. 保存完整清单
    print(f"\n步骤5: 保存完整应用清单...")

    # 好客户独有应用
    good_only_records = []
    for app, count in sorted(good_only.items(), key=lambda x: x[1], reverse=True):
        good_only_records.append({
            'app': app,
            'good_count': count,
            'bad_count': 0,
            'total_count': count,
            'good_rate_pct': round(count / len(good_order_ids) * 100, 4),
            'bad_rate_pct': 0.0,
            'risk_ratio': 0.0
        })

    good_only_df = pd.DataFrame(good_only_records)
    good_only_df.to_csv('outputs/app_analysis/good_customer_apps_complete.csv', index=False)
    print(f"   ✓ 好客户应用保存: {len(good_only_df)} 个")

    # 坏客户独有应用
    bad_only_records = []
    for app, count in sorted(bad_only.items(), key=lambda x: x[1], reverse=True):
        bad_only_records.append({
            'app': app,
            'good_count': 0,
            'bad_count': count,
            'total_count': count,
            'good_rate_pct': 0.0,
            'bad_rate_pct': round(count / len(bad_order_ids) * 100, 4),
            'risk_ratio': 999.99
        })

    bad_only_df = pd.DataFrame(bad_only_records)
    bad_only_df.to_csv('outputs/app_analysis/bad_customer_apps_complete.csv', index=False)
    print(f"   ✓ 坏客户应用保存: {len(bad_only_df)} 个")

    # 共有应用
    common_records = []
    for app in common.keys():
        g_count = good_apps[app]
        b_count = bad_apps[app]
        total = g_count + b_count
        g_rate = round(g_count / len(good_order_ids) * 100, 4)
        b_rate = round(b_count / len(bad_order_ids) * 100, 4)
        ratio = round(b_rate / g_rate, 2) if g_rate > 0 else 999.99

        common_records.append({
            'app': app,
            'good_count': g_count,
            'bad_count': b_count,
            'total_count': total,
            'good_rate_pct': g_rate,
            'bad_rate_pct': b_rate,
            'risk_ratio': ratio
        })

    common_df = pd.DataFrame(common_records)
    common_df = common_df.sort_values('total_count', ascending=False)
    common_df.to_csv('outputs/app_analysis/common_apps_complete.csv', index=False)
    print(f"   ✓ 共有应用保存: {len(common_df)} 个")

    print("\n" + "="*80)
    print("完整应用清单提取完成！")
    print("="*80)
    print(f"\n文件保存到 outputs/app_analysis/:")
    print(f"  - good_customer_apps_complete.csv: {len(good_only_df)} 个应用")
    print(f"  - bad_customer_apps_complete.csv: {len(bad_only_df)} 个应用")
    print(f"  - common_apps_complete.csv: {len(common_df)} 个应用")


if __name__ == '__main__':
    main()
