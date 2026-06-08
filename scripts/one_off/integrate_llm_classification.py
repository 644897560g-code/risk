"""
整合LLM应用分类结果到知识库

脚本功能：
1. 读取全量数据分析结果（outputs/app_analysis/）
2. 提取LLM分类的高风险应用列表
3. 更新到知识库JSON文件
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(__file__))

def integrate_classification():
    """整合LLM分类结果到知识库"""

    # 读取知识库
    kb_path = "outputs/knowledge_base/knowledge_base.json"
    if not os.path.exists(kb_path):
        print(f"知识库文件不存在: {kb_path}")
        return

    with open(kb_path, 'r', encoding='utf-8') as f:
        kb_data = json.load(f)

    # 读取LLM分类结果
    classification_path = "outputs/app_analysis/app_classification_result.json"
    with open(classification_path, 'r', encoding='utf-8') as f:
        classification_data = json.load(f)

    classifications = classification_data.get('classifications', {})

    # 定义高风险类别
    high_risk_categories = ['gambling', 'fintech_lending', 'cash_loan', 'installment']

    # 提取高风险应用列表（基于LLM分类）
    high_risk_apps = []
    for app, info in classifications.items():
        category = info.get('category', '')
        confidence = info.get('confidence', '')

        if category in high_risk_categories and confidence in ['high', 'medium']:
            high_risk_apps.append({
                'package': app,
                'category': category,
                'confidence': confidence,
                'reason': info.get('reason', '')
            })

    # 按类别分组
    category_groups = {}
    for app_info in high_risk_apps:
        cat = app_info['category']
        if cat not in category_groups:
            category_groups[cat] = []
        category_groups[cat].append(app_info)

    print(f"\n{'='*80}")
    print(f"LLM分类结果整合到知识库")
    print(f"{'='*80}")
    print(f"总高风险应用数: {len(high_risk_apps)}")
    print(f"\n高风险类别分布:")
    for cat, apps in category_groups.items():
        print(f"  {cat}: {len(apps)} 个应用")

    # 更新知识库
    kb = kb_data.get('knowledge_base', {})

    # 更新高风险应用列表
    kb['app_analysis']['high_risk_app_list'] = [app['package'] for app in high_risk_apps[:30]]  # 取前30个

    # 添加LLM分类元数据
    kb['app_analysis']['llm_classification'] = {
        'method': 'LLM_SCIENCE_CLASSIFICATION',
        'model': 'qwen/qwen3.6-plus',
        'classification_date': '2026-04-26',
        'total_classified_apps': len(classifications),
        'high_risk_categories': list(category_groups.keys()),
        'high_risk_apps_by_category': {
            cat: [app['package'] for app in apps]
            for cat, apps in category_groups.items()
        },
        'key_insights': classification_data.get('summary', {}).get('key_insights', '')
    }

    # 保存更新后的知识库
    with open(kb_path, 'w', encoding='utf-8') as f:
        json.dump(kb_data, f, ensure_ascii=False, indent=2)

    print(f"\n知识库已更新: {kb_path}")
    print(f"高风险应用列表: {len(kb['app_analysis']['high_risk_app_list'])} 个")

    return kb_data


if __name__ == '__main__':
    integrate_classification()
