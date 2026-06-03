"""
FDC数据结构分析工具 - Day 3-4任务

功能：
1. 加载样本短链数据
2. 解析FDC数据结构
3. 分析各字段的可特征化潜力
4. 生成FDC特征设计方案
"""

import json
import os
import requests
from typing import Dict, List

def load_sample_fdc(sample_url: str) -> Dict:
    """从短链加载单个样本的FDC数据"""
    print(f"加载样本: {sample_url}")
    response = requests.get(sample_url)
    data = response.json()

    fdc_data = data.get('params', {}).get('FDC', {})
    return fdc_data


def analyze_fdc_structure(fdc_data: Dict) -> Dict:
    """分析FDC数据结构"""
    analysis = {
        "top_level_keys": list(fdc_data.keys()),
        "details": {}
    }

    for key, value in fdc_data.items():
        if isinstance(value, dict):
            analysis["details"][key] = {
                "type": "dict",
                "keys": list(value.keys()),
                "sample_data": dict(list(value.items())[:3])  # 取前3个字段作为示例
            }
        elif isinstance(value, list):
            analysis["details"][key] = {
                "type": "list",
                "length": len(value),
                "sample_item": value[0] if value else None
            }
        else:
            analysis["details"][key] = {
                "type": type(value).__name__,
                "value": value
            }

    return analysis


def design_fdc_features(analysis: Dict) -> List[Dict]:
    """基于FDC分析设计特征"""
    features = []

    # 1. pinjaman（贷款记录）特征
    if 'pinjaman' in analysis['details']:
        pinjaman_info = analysis['details']['pinjaman']
        features.extend([
            {
                "name": "count_pinjaman_total",
                "type": "count",
                "source": "pinjaman",
                "formula": "len(pinjaman)",
                "description": "总贷款笔数",
                "business_value": "贷款次数越多，风险可能越高"
            },
            {
                "name": "count_pinjaman_platforms",
                "type": "count_unique",
                "source": "pinjaman",
                "formula": "len(unique(platform_name))",
                "description": "贷款平台数量",
                "business_value": "多平台借贷风险更高"
            },
            {
                "name": "ratio_pinjaman_overdue",
                "type": "ratio",
                "source": "pinjaman",
                "formula": "count(overdue) / count(pinjaman)",
                "description": "逾期比例",
                "business_value": "历史逾期比例高的用户风险更高"
            },
            {
                "name": "amt_pinjaman_avg",
                "type": "avg",
                "source": "pinjaman",
                "formula": "avg(loan_amount)",
                "description": "平均贷款金额",
                "business_value": "贷款金额大的用户需要关注"
            },
            {
                "name": "days_since_last_loan",
                "type": "days_diff",
                "source": "pinjaman",
                "formula": "max(loan_date)到申请日的天数",
                "description": "距最近贷款的天数",
                "business_value": "最近有贷款的用户可能更急需资金"
            }
        ])

    # 2. history_inquiry（查询历史）特征
    if 'history_inquiry' in analysis['details']:
        inquiry_info = analysis['details']['history_inquiry']
        features.extend([
            {
                "name": "count_inquiry_total",
                "type": "count",
                "source": "history_inquiry",
                "formula": "len(history_inquiry)",
                "description": "总查询次数",
                "business_value": "频繁查询可能预示资金紧张"
            },
            {
                "name": "count_inquiry_3d",
                "type": "count_time_window",
                "source": "history_inquiry",
                "formula": "count(inquiry where date >= now - 3 days)",
                "description": "近3天查询次数",
                "business_value": "短期内密集查询风险更高"
            },
            {
                "name": "count_inquiry_7d",
                "type": "count_time_window",
                "source": "history_inquiry",
                "formula": "count(inquiry where date >= now - 7 days)",
                "description": "近7天查询次数",
                "business_value": "近一周查询活跃度"
            },
            {
                "name": "count_inquiry_institutions_7d",
                "type": "count_unique",
                "source": "history_inquiry",
                "formula": "len(unique(institution where date >= now - 7 days))",
                "description": "近7天查询机构数",
                "business_value": "多机构查询风险更高"
            },
            {
                "name": "ratio_inquiry_fintech",
                "type": "ratio",
                "source": "history_inquiry",
                "formula": "count(fintech_institutions) / count(all_institutions)",
                "description": "金融科技公司查询占比",
                "business_value": "Fintech查询占比高可能风险更高"
            }
        ])

    # 3. platform_aktif（活跃平台）特征
    if 'platform_aktif' in analysis['details']:
        platform_info = analysis['details']['platform_aktif']
        features.extend([
            {
                "name": "count_platform_active",
                "type": "count",
                "source": "platform_aktif",
                "formula": "len(platform_aktif)",
                "description": "活跃平台数量",
                "business_value": "活跃平台多，可能有多头借贷"
            },
            {
                "name": "amt_platform_active_total",
                "type": "sum",
                "source": "platform_aktif",
                "formula": "sum(active_loan_amount)",
                "description": "在贷总金额",
                "business_value": "在贷金额大的用户负债高"
            }
        ])

    return features


def save_fdc_features(features: List[Dict]):
    """保存FDC特征设计"""
    os.makedirs('outputs/fdc_analysis', exist_ok=True)

    with open('outputs/fdc_analysis/fdc_features.json', 'w', encoding='utf-8') as f:
        json.dump(features, f, ensure_ascii=False, indent=2)

    print(f"✅ 保存了{len(features)}个FDC特征设计")


if __name__ == '__main__':
    print("=" * 70)
    print("FDC数据结构分析工具 - Day 3-4")
    print("=" * 70)

    # 样本URL（第一个样本）
    sample_url = "https://ng-fenqi-prod-1320687172.oss-us-west-1.aliyuncs.com/Apply/order-formatfile/id002luzt202603090951432723072"

    # 1. 加载FDC数据
    fdc_data = load_sample_fdc(sample_url)

    # 2. 分析结构
    print("\n正在分析FDC数据结构...")
    analysis = analyze_fdc_structure(fdc_data)

    print(f"\nFDC顶层字段: {analysis['top_level_keys']}")
    print(f"\n详细结构:")
    for key, detail in analysis['details'].items():
        print(f"  {key}: {detail['type']} - {detail.get('keys', 'N/A')[:5]}")

    # 3. 设计FDC特征
    print("\n正在设计FDC特征...")
    fdc_features = design_fdc_features(analysis)

    # 4. 保存
    save_fdc_features(fdc_features)

    print("\nFDC特征设计预览:")
    for feature in fdc_features:
        print(f"  - {feature['name']}: {feature['description']}")

    print("\n" + "=" * 70)
    print("Day 3-4任务完成!")
    print("=" * 70)
