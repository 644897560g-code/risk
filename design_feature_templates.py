"""
特征模板设计工具 - Day 1任务

功能：
1. 分析现有20个特征
2. 设计特征模板
3. 保存模板配置
"""

import json
import os

# 现有的20个特征设计（从之前的执行结果）
EXISTING_FEATURES = [
    # 这里会从之前的execution中获取
    # 暂时使用占位符
]

# 模板设计
def create_ratio_template():
    """比例类特征模板"""
    return {
        "template_id": "ratio_{metric}_{source}_{period}",
        "template_name": "{source}_{metric}占比_{period}天",
        "category": "ratio_feature",
        "parameters": {
            "metric": ["count", "sum", "avg"],
            "source": ["fdc_loan", "applist_gambling", "applist_cashloan"],
            "period": [3, 7, 30, 90]
        },
        "formula": "近{period}天{source}的{metric} / 总体{source}的{metric}",
        "description": "反映用户近{period}天内{source}的活跃程度",
        "business_value": "时间窗口越短，风险敏感性越高",
        "data_source": ["FDC", "applist"],
        "anti_penetration": True  # 防穿越
    }


def create_count_template():
    """统计类特征模板"""
    return {
        "template_id": "count_{metric}_{source}_{period}",
        "template_name": "{source}_{metric}_近{period}天",
        "category": "count_feature",
        "parameters": {
            "metric": ["total", "unique", "avg_per_day"],
            "source": ["fdc_inquiry", "pinjaman_active", "applist_category"],
            "period": [1, 3, 7, 30, 90]
        },
        "formula": "{source}的{metric}（近{period}天）",
        "description": "统计近{period}天内{source}的{metric}",
        "business_value": "绝对数量反映用户行为强度",
        "data_source": ["FDC", "applist"],
        "anti_penetration": True
    }


def create_cross_template():
    """交叉类特征模板"""
    return {
        "template_id": "cross_{base_field}_{source_metric}",
        "template_name": "交叉_{base_field}_{source_metric}",
        "category": "cross_feature",
        "parameters": {
            "base_field": ["age", "gender", "salary", "marriage", "work_years"],
            "source_metric": [
                "fdc_loan_count",
                "applist_gambling_ratio",
                "fdc_inquiry_7d"
            ]
        },
        "formula": "{base_field}分组 × {source_metric}",
        "description": "不同{base_field}人群的{source_metric}差异",
        "business_value": "发现高风险人群的细粒度特征",
        "data_source": ["base", "FDC", "applist"],
        "anti_penetration": True
    }


def create_trend_template():
    """趋势类特征模板"""
    return {
        "template_id": "trend_{source}_{metric}_{short_period}_vs_{long_period}",
        "template_name": "趋势_{source}_{metric}_{short_period}天vs{long_period}天",
        "category": "trend_feature",
        "parameters": {
            "source": ["fdc_loan", "fdc_inquiry", "applist_install"],
            "metric": ["count", "sum"],
            "period_pair": [
                ("3", "7"),
                ("7", "30"),
                ("30", "90")
            ]
        },
        "formula": "近{short_period}天{source}_{metric} / 近{long_period}天{source}_{metric}",
        "description": "近期vs长期的{source}_{metric}变化趋势",
        "business_value": "趋势上升可能预示风险增加",
        "data_source": ["FDC", "applist"],
        "anti_penetration": True
    }


def generate_templates():
    """生成所有模板"""
    templates = {
        "ratio": create_ratio_template(),
        "count": create_count_template(),
        "cross": create_cross_template(),
        "trend": create_trend_template()
    }

    # 保存到文件
    os.makedirs('outputs/feature_templates', exist_ok=True)
    for name, template in templates.items():
        filepath = f'outputs/feature_templates/{name}_template.json'
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(template, f, ensure_ascii=False, indent=2)

    print(f"✅ 保存了{len(templates)}个模板到 outputs/feature_templates/")
    return templates


if __name__ == '__main__':
    print("=" * 70)
    print("特征模板设计工具 - Day 1")
    print("=" * 70)

    templates = generate_templates()

    print("\n模板列表:")
    for name, template in templates.items():
        print(f"  - {name}: {template['template_name']}")
