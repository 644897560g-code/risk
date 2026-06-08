"""
分析第10批分类结果（前2,000个应用）

验证分类质量、类别分布、高风险类别识别准确度
"""

import json
import pandas as pd
from collections import Counter, defaultdict
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def analyze_classification_quality(result_file: str):
    """分析分类结果质量"""

    logger.info("="*80)
    logger.info("分析第10批分类结果（前2,000个应用）")
    logger.info("="*80)

    # 1. 加载数据
    logger.info("\n步骤1: 加载数据...")
    with open(result_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    classifications = data.get('classifications', data)  # 兼容两种格式
    total_apps = len(classifications)

    logger.info(f"   总应用数: {total_apps:,}")

    # 2. 类别分布统计
    logger.info("\n步骤2: 类别分布统计...")
    category_counts = Counter([v['category'] for v in classifications.values()])
    confidence_counts = Counter([v['confidence'] for v in classifications.values()])

    logger.info(f"\n类别分布（按数量排序）:")
    logger.info(f"  {'类别':30s} {'数量':>8s} {'占比':>8s}")
    logger.info(f"  {'-'*50}")

    for cat, count in category_counts.most_common():
        pct = count / total_apps * 100
        logger.info(f"  {cat:30s} {count:8,} {pct:7.2f}%")

    logger.info(f"\n置信度分布:")
    for conf, count in confidence_counts.most_common():
        pct = count / total_apps * 100
        logger.info(f"  {conf:15s} {count:8,} {pct:7.2f}%")

    # 3. 高风险类别分析
    logger.info("\n步骤3: 高风险类别分析...")
    high_risk_categories = ['cash_loan', 'fintech_lending', 'gambling', 'fake_gps', 'app_store', 'clone_app']

    high_risk_apps = []
    for app, info in classifications.items():
        if info['category'] in high_risk_categories:
            high_risk_apps.append({
                'app': app,
                'category': info['category'],
                'confidence': info['confidence'],
                'reason': info['reason']
            })

    logger.info(f"  高风险类别应用数: {len(high_risk_apps)} ({len(high_risk_apps)/total_apps*100:.2f}%)")
    logger.info(f"\n高风险类别分布:")
    hr_category_counts = Counter([app['category'] for app in high_risk_apps])
    for cat, count in hr_category_counts.most_common():
        logger.info(f"  {cat:30s} {count:8,}")

    # 4. 抽样检查高风险应用
    logger.info("\n步骤4: 高风险应用抽样检查...")
    sample_size = min(10, len(high_risk_apps))
    logger.info(f"  抽样检查 {sample_size} 个高风险应用:\n")

    for app in high_risk_apps[:sample_size]:
        logger.info(f"  应用: {app['app']}")
        logger.info(f"  类别: {app['category']}")
        logger.info(f"  置信度: {app['confidence']}")
        logger.info(f"  理由: {app['reason']}")
        logger.info(f"  {'-'*60}")

    # 5. 检查未知类别
    logger.info("\n步骤5: 检查类别有效性...")
    valid_categories = {
        'cash_loan', 'fintech_lending', 'gambling', 'fake_gps', 'app_store',
        'clone_app', 'banking', 'ewallet', 'installment', 'shopping',
        'transportation', 'food_delivery', 'utility', 'social_entertainment',
        'productivity', 'religious', 'other'
    }

    unknown_cats = [cat for cat in category_counts.keys() if cat not in valid_categories]
    if unknown_cats:
        logger.warning(f"  ⚠ 发现未知类别: {unknown_cats}")
    else:
        logger.info(f"  ✓ 所有类别都在标准列表中")

    # 6. 完整应用列表对比
    logger.info("\n步骤6: 与完整应用清单对比...")
    try:
        full_apps_df = pd.read_csv('outputs/app_analysis/good_customer_apps_complete.csv')
        bad_apps_df = pd.read_csv('outputs/app_analysis/bad_customer_apps_complete.csv')
        common_apps_df = pd.read_csv('outputs/app_analysis/common_apps_complete.csv')

        all_apps = pd.concat([full_apps_df, bad_apps_df, common_apps_df])
        classified_apps_in_result = [app for app in classifications.keys() if app in all_apps['app'].values]

        logger.info(f"  完整应用清单中的应用数: {len(all_apps)}")
        logger.info(f"  本次分类结果中的应用数: {total_apps}")
        logger.info(f"  匹配上的应用数: {len(classified_apps_in_result)}")

        if len(classified_apps_in_result) < total_apps:
            logger.warning(f"  ⚠ 有 {total_apps - len(classified_apps_in_result)} 个应用不在完整清单中")
    except Exception as e:
        logger.warning(f"  ⚠ 无法加载完整应用清单: {e}")

    # 7. 生成分析报告
    logger.info("\n步骤7: 生成分析报告...")
    report_path = 'outputs/app_analysis/batch10_analysis_report.json'

    report = {
        'batch_info': {
            'batches_completed': 10,
            'apps_classified': total_apps,
            'analysis_timestamp': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        'category_distribution': dict(category_counts.most_common()),
        'confidence_distribution': dict(confidence_counts.most_common()),
        'high_risk_analysis': {
            'total_high_risk': len(high_risk_apps),
            'percentage': len(high_risk_apps) / total_apps * 100,
            'category_breakdown': dict(hr_category_counts.most_common()),
            'sample_apps': high_risk_apps[:sample_size]
        },
        'quality_check': {
            'valid_categories': len(unknown_cats) == 0,
            'unknown_categories': unknown_cats
        }
    }

    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"  ✓ 分析报告已保存: {report_path}")

    # 8. 生成CSV便于查看
    logger.info("\n步骤8: 生成CSV文件...")
    csv_path = 'outputs/app_analysis/batch10_classifications.csv'

    rows = []
    for app, info in classifications.items():
        rows.append({
            'app_package': app,
            'category': info['category'],
            'confidence': info['confidence'],
            'reason': info['reason']
        })

    df = pd.DataFrame(rows)
    df = df.sort_values('category')
    df.to_csv(csv_path, index=False)
    logger.info(f"  ✓ CSV文件已保存: {csv_path}")

    logger.info("\n" + "="*80)
    logger.info("分析完成！")
    logger.info("="*80)

    return report


if __name__ == '__main__':
    result_file = 'outputs/app_analysis/classification_intermediate_batch10.json'

    try:
        report = analyze_classification_quality(result_file)
    except FileNotFoundError:
        logger.error(f"错误: 文件 {result_file} 不存在")
        logger.info("请等待第10批完成后重新运行")
    except Exception as e:
        logger.error(f"分析失败: {e}")
        import traceback
        traceback.print_exc()
