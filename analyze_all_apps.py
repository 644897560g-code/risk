"""
全量样本应用分析 - 好坏客户applist对比

基于全部2916条短链数据，统计好坏客户的应用安装差异
"""

import sys
import os
import json
import pandas as pd
from collections import Counter
sys.path.insert(0, os.path.dirname(__file__))

from data.data_loader import DataLoader, ShortLinkFetcher

# 配置日志
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    logger.info("="*80)
    logger.info("全量样本应用分析 - 好坏客户对比")
    logger.info("="*80)

    # 1. 加载数据
    logger.info("步骤1: 加载数据...")
    loader = DataLoader()
    fetcher = ShortLinkFetcher()

    short_links = loader.load_short_links()
    model_samples = loader.load_model_samples()

    logger.info(f"   短链总数: {len(short_links)}")
    logger.info(f"   建模样本: {len(model_samples)}")

    # 2. 分离好坏客户
    good_customers = model_samples[model_samples['is_overdue'] == 0]
    bad_customers = model_samples[model_samples['is_overdue'] == 1]

    good_order_ids = set(good_customers['source_order_no'].tolist())
    bad_order_ids = set(bad_customers['source_order_no'].tolist())

    logger.info(f"   好客户: {len(good_order_ids)}")
    logger.info(f"   坏客户: {len(bad_order_ids)}")

    # 3. 批量获取JSON数据
    logger.info(f"步骤2: 从{len(short_links)}条短链中获取JSON数据（可能需要几分钟）...")
    json_data_list = fetcher.fetch_batch(short_links)
    logger.info(f"   成功获取: {len(json_data_list)} 条JSON数据")

    # 4. 分别提取好坏客户的app
    logger.info("步骤3: 提取应用列表...")
    good_apps = []
    bad_apps = []
    unknown_apps = []  # 订单ID不在建模样本中的

    for i, data in enumerate(json_data_list):
        order_id = data.get('orderId', '')
        app_list = data.get('params', {}).get('appList', [])
        packages = [app.get('packageX', '') for app in app_list if app.get('packageX')]

        if order_id in good_order_ids:
            good_apps.extend(packages)
        elif order_id in bad_order_ids:
            bad_apps.extend(packages)
        else:
            unknown_apps.extend(packages)

        if (i + 1) % 500 == 0:
            logger.info(f"   已处理: {i+1}/{len(json_data_list)}")

    logger.info(f"   好客户应用记录: {len(good_apps)}")
    logger.info(f"   坏客户应用记录: {len(bad_apps)}")
    logger.info(f"   未知客户应用记录: {len(unknown_apps)}")

    # 5. 去重统计
    good_apps_unique = set(good_apps)
    bad_apps_unique = set(bad_apps)
    all_apps_unique = good_apps_unique | bad_apps_unique

    common_apps = good_apps_unique & bad_apps_unique
    good_only = good_apps_unique - bad_apps_unique
    bad_only = bad_apps_unique - good_apps_unique

    logger.info(f"   好客户独立应用: {len(good_apps_unique)}")
    logger.info(f"   坏客户独立应用: {len(bad_apps_unique)}")
    logger.info(f"   共有应用: {len(common_apps)}")
    logger.info(f"   好客户独有: {len(good_only)}")
    logger.info(f"   坏客户独有: {len(bad_only)}")
    logger.info(f"   总独立应用数: {len(all_apps_unique)}")

    # 6. 频次统计
    logger.info("步骤4: 计算应用频次...")
    good_app_counts = Counter(good_apps)
    bad_app_counts = Counter(bad_apps)

    # 7. 计算每个应用的好坏客户安装率
    logger.info("步骤5: 计算风险指标...")

    app_stats = []
    for app in all_apps_unique:
        good_count = good_app_counts.get(app, 0)
        bad_count = bad_app_counts.get(app, 0)
        total_count = good_count + bad_count

        good_rate = good_count / len(good_apps) * 100 if len(good_apps) > 0 else 0
        bad_rate = bad_count / len(bad_apps) * 100 if len(bad_apps) > 0 else 0

        # 坏客户倾向度
        if good_rate > 0:
            risk_ratio = bad_rate / good_rate
        else:
            risk_ratio = float('inf') if bad_rate > 0 else 0

        app_stats.append({
            'app': app,
            'good_count': good_count,
            'bad_count': bad_count,
            'total_count': total_count,
            'good_rate_pct': round(good_rate, 4),
            'bad_rate_pct': round(bad_rate, 4),
            'risk_ratio': round(risk_ratio, 2) if risk_ratio != float('inf') else 999.99
        })

    # 转为DataFrame方便分析
    df_apps = pd.DataFrame(app_stats)

    # 8. Top 100 高风险应用（坏客户倾向度最高）
    logger.info("步骤6: 生成报告...")
    df_high_risk = df_apps[
        (df_apps['total_count'] >= 3) &  # 至少安装3次
        (df_apps['bad_count'] > 0)  # 坏客户有安装
    ].sort_values('risk_ratio', ascending=False).head(100)

    # 9. Top 50 好客户独有应用（可能是保护性应用）
    df_good_only = df_apps[
        (df_apps['good_count'] > 0) &
        (df_apps['bad_count'] == 0)
    ].sort_values('good_count', ascending=False).head(50)

    # 10. Top 100 高频共有应用
    df_common = df_apps[
        (df_apps['good_count'] > 0) &
        (df_apps['bad_count'] > 0)
    ].sort_values('total_count', ascending=False).head(100)

    # 11. 输出结果
    logger.info("="*80)
    logger.info("分析完成")
    logger.info("="*80)

    print("\n【Top 50 高风险应用 - 坏客户倾向度最高】")
    print("-" * 120)
    for i, row in df_high_risk.head(50).iterrows():
        print(f"  {i+1:3d}. {row['app']:70s} "
              f"坏:{row['bad_count']:3d}({row['bad_rate_pct']:5.2f}%) "
              f"好:{row['good_count']:3d}({row['good_rate_pct']:5.2f}%) "
              f"比率:{row['risk_ratio']:8.1f}x")

    print("\n【Top 30 好客户独有应用 - 可能是保护性应用】")
    print("-" * 120)
    for i, row in df_good_only.head(30).iterrows():
        print(f"  {i+1:3d}. {row['app']:70s} 好:{row['good_count']:3d}次")

    print("\n【Top 30 高频共有应用】")
    print("-" * 120)
    for i, row in df_common.head(30).iterrows():
        print(f"  {row['app']:70s} "
              f"总:{row['total_count']:3d} "
              f"坏:{row['bad_count']:3d}({row['bad_rate_pct']:5.2f}%) "
              f"好:{row['good_count']:3d}({row['good_rate_pct']:5.2f}%)")

    # 12. 保存详细结果
    output_dir = "outputs/app_analysis"
    os.makedirs(output_dir, exist_ok=True)

    df_high_risk.to_csv(f"{output_dir}/high_risk_apps.csv", index=False)
    df_good_only.to_csv(f"{output_dir}/good_only_apps.csv", index=False)
    df_common.to_csv(f"{output_dir}/common_apps.csv", index=False)

    # 保存汇总统计
    summary = {
        'total_samples': len(json_data_list),
        'good_customers': len(good_order_ids),
        'bad_customers': len(bad_order_ids),
        'good_app_records': len(good_apps),
        'bad_app_records': len(bad_apps),
        'unique_apps': {
            'total': len(all_apps_unique),
            'good_only': len(good_only),
            'bad_only': len(bad_only),
            'common': len(common_apps)
        },
        'top_high_risk_apps': df_high_risk.head(50).to_dict('records'),
        'top_good_only_apps': df_good_only.head(30).to_dict('records')
    }

    with open(f"{output_dir}/app_analysis_summary.json", 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    logger.info(f"\n结果已保存到: {output_dir}/")
    logger.info(f"   - high_risk_apps.csv (高风险应用)")
    logger.info(f"   - good_only_apps.csv (好客户独有应用)")
    logger.info(f"   - common_apps.csv (共有应用)")
    logger.info(f"   - app_analysis_summary.json (完整汇总)")

    return summary


if __name__ == '__main__':
    main()
