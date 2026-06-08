"""
生成50个测试特征方案 - 综合所有模板

包括：
- FDC特征（12个，已有）
- Applist特征（15个）
- Base特征（8个）
- 交叉特征（10个）
- 趋势特征（5个）
"""

import json
import os
from itertools import product

def load_fdc_features():
    """加载FDC特征"""
    with open('outputs/fdc_analysis/fdc_features.json', 'r', encoding='utf-8') as f:
        return json.load(f)


def generate_applist_features():
    """生成Applist特征（15个）"""
    features = []

    categories = ['gambling', 'cash_loan', 'fintech', 'banking', 'shopping']
    metrics = ['count', 'ratio', 'avg_days_since_update']

    # 每个类别3个指标
    for cat in categories:
        for metric in metrics:
            features.append({
                "name": f"{metric}_applist_{cat}",
                "type": "applist_stat",
                "source": "applist",
                "formula": f"计算{cat}类别APP的{metric}",
                "description": f"{cat}类别APP的{metric}指标",
                "business_value": f"风险类别APP反映用户偏好"
            })

    return features[:15]


def generate_base_features():
    """生成Base基础特征（8个）"""
    return [
        {
            "name": "age_group",
            "type": "binned",
            "source": "base.birthday",
            "formula": "根据生日计算年龄段",
            "description": "用户年龄段",
            "business_value": "不同年龄段风险不同"
        },
        {
            "name": "salary_level",
            "type": "binned",
            "source": "base.salary",
            "formula": "薪资分层",
            "description": "用户薪资水平",
            "business_value": "收入影响还款能力"
        },
        {
            "name": "work_years_category",
            "type": "categorical",
            "source": "base.workYears",
            "formula": "工作年限分类",
            "description": "工作年限",
            "business_value": "工作稳定性影响信用"
        },
        {
            "name": "gender",
            "type": "categorical",
            "source": "base.gender",
            "formula": "性别",
            "description": "用户性别",
            "business_value": "性别可能与风险相关"
        },
        {
            "name": "marriage_status",
            "type": "categorical",
            "source": "base.marita",
            "formula": "婚姻状态",
            "description": "婚姻状态",
            "business_value": "已婚用户可能更稳定"
        },
        {
            "name": "has_children",
            "type": "binary",
            "source": "base.children",
            "formula": "是否有子女",
            "description": "是否有子女",
            "business_value": "有子女用户责任更大"
        },
        {
            "name": "job_type",
            "type": "categorical",
            "source": "base.job",
            "formula": "职业类型",
            "description": "职业类型",
            "business_value": "职业影响收入稳定性"
        },
        {
            "name": "salary_to_loan_ratio",
            "type": "ratio",
            "source": "base.salary",
            "formula": "薪资/平均贷款金额",
            "description": "收入负债比",
            "business_value": "衡量还款能力"
        }
    ]


def generate_cross_features(fdc_features):
    """生成交叉特征（10个）"""
    features = []

    # base × fdc 交叉
    base_fields = ['age_group', 'salary_level', 'gender', 'marriage_status']
    fdc_metrics = ['count_pinjaman_total', 'count_inquiry_7d', 'ratio_pinjaman_overdue']

    for base_f, fdc_m in product(base_fields[:3], fdc_metrics[:3]):
        features.append({
            "name": f"cross_{base_f}_{fdc_m}",
            "type": "cross",
            "source": ["base", "FDC"],
            "formula": f"分组统计: {base_f} × {fdc_m}",
            "description": f"不同{base_f}人群的{fdc_m}差异",
            "business_value": "细粒度风险分层"
        })

        if len(features) >= 10:
            break

    return features


def generate_trend_features():
    """生成趋势特征（5个）"""
    return [
        {
            "name": "trend_inquiry_3d_vs_7d",
            "type": "trend",
            "source": "history_inquiry",
            "formula": "近3天查询次数 / 近7天查询次数",
            "description": "查询短期趋势",
            "business_value": "趋势上升预示风险增加"
        },
        {
            "name": "trend_loan_7d_vs_30d",
            "type": "trend",
            "source": "pinjaman",
            "formula": "近7天贷款数 / 近30天贷款数",
            "description": "贷款趋势",
            "business_value": "贷款频率变化"
        },
        {
            "name": "trend_applist_install_trend",
            "type": "trend",
            "source": "applist",
            "formula": "近3天安装斜率",
            "description": "APP安装趋势",
            "business_value": "近期安装行为变化"
        },
        {
            "name": "trend_inquiry_slope",
            "type": "trend",
            "source": "history_inquiry",
            "formula": "查询次数线性回归斜率",
            "description": "查询趋势斜率",
            "business_value": "斜率为正表示风险上升"
        },
        {
            "name": "trend_loan_slope",
            "type": "trend",
            "source": "pinjaman",
            "formula": "贷款次数线性回归斜率",
            "description": "贷款趋势斜率",
            "business_value": "贷款频率增长趋势"
        }
    ]


def generate_all_features():
    """生成所有50个测试特征"""
    all_features = []

    # 1. FDC特征（12个）
    fdc_feats = load_fdc_features()
    all_features.extend(fdc_feats)
    print(f"FDC特征: {len(fdc_feats)}个")

    # 2. Applist特征（15个）
    applist_feats = generate_applist_features()
    all_features.extend(applist_feats)
    print(f"Applist特征: {len(applist_feats)}个")

    # 3. Base特征（8个）
    base_feats = generate_base_features()
    all_features.extend(base_feats)
    print(f"Base特征: {len(base_feats)}个")

    # 4. 交叉特征（10个）
    cross_feats = generate_cross_features(fdc_feats)
    all_features.extend(cross_feats)
    print(f"交叉特征: {len(cross_feats)}个")

    # 5. 趋势特征（5个）
    trend_feats = generate_trend_features()
    all_features.extend(trend_feats)
    print(f"趋势特征: {len(trend_feats)}个")

    return all_features


if __name__ == '__main__':
    print("=" * 70)
    print("生成50个测试特征方案")
    print("=" * 70)

    features = generate_all_features()

    # 保存
    os.makedirs('outputs/feature_design', exist_ok=True)
    output_file = 'outputs/feature_design/designs_50.json'

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(features, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 保存了{len(features)}个特征设计方案到 {output_file}")

    # 按类别统计
    categories = {}
    for feat in features:
        cat = feat.get('type', 'unknown')
        categories[cat] = categories.get(cat, 0) + 1

    print("\n特征类别统计:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}个")

    print("\n" + "=" * 70)
