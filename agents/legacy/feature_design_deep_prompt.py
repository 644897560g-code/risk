"""
深度业务驱动的特征设计Prompt构建器

目标: 基于印尼现金贷风控的深度理解，设计可扩展的特征框架
原则: 1. 业务逻辑通用  2. 数据动态传入  3. 不写死任何数字
"""

import os
import sys
import json
from typing import Dict, List, Any

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agents.legacy.feature_design_deep_prompt_helpers import format_age_risk_dynamic


def build_deep_business_prompt(knowledge_base: Dict, fdc_variables: List[str]) -> str:
    """
    构建深度业务驱动的Prompt

    Args:
        knowledge_base: 数据分析Agent输出的完整知识库
        fdc_variables: FDC现有特征变量列表

    Returns:
        Prompt文本
    """

    kb = knowledge_base.get('knowledge_base', {})
    summary = kb.get('summary', {})
    base_analysis = kb.get('base_analysis', {})
    app_analysis = kb.get('app_analysis', {})
    fdc_analysis = kb.get('fdc_analysis', {})
    risk_rules = kb.get('risk_rules', [])

    # 构建Prompt
    return f"""# 任务：设计印尼现金贷风控的**特征框架体系**

## 业务背景（基于{summary.get('total_samples', 'N/A')}个样本、{summary.get('overdue_rate', 0) * 100:.1f}%逾期率）

### 关键风险信号（全部动态传入）

**1. 客户画像风险分层**:
- 性别差异: 男性{base_analysis.get('gender_risk', {}).get('male_overdue_rate', 0) * 100:.1f}%，女性{base_analysis.get('gender_risk', {}).get('female_overdue_rate', 0) * 100:.1f}%（{base_analysis.get('gender_risk', {}).get('risk_ratio', 0):.1f}倍）
- 年龄模式: {format_age_risk_dynamic(base_analysis.get('age_risk_bins', []))}
- 收入效应: 相关系数{base_analysis.get('income_risk_correlation', 'N/A')}

**2. 多头借贷**（印尼现金贷最核心风险）
- FDC查询: 近3天{fdc_analysis.get('query_freq_risk', {}).get('last_3days_avg', 'N/A')}次，近7天{fdc_analysis.get('query_freq_risk', {}).get('last_7days_avg', 'N/A')}次，近30天{fdc_analysis.get('query_freq_risk', {}).get('last_30days_avg', 'N/A')}次
- 活跃平台: {fdc_analysis.get('loan_record_stats', {}).get('avg_active_platforms', 'N/A')}个，在贷余额{fdc_analysis.get('loan_record_stats', {}).get('avg_outstanding_balance', 0):,.0f}印尼盾
- 逾期严重度: 最大DPD{fdc_analysis.get('dpd_analysis', {}).get('avg_max_dpd', 'N/A')}天，30天+占比{fdc_analysis.get('dpd_analysis', {}).get('dpd_30plus_ratio', 0) * 100:.0f}%

**3. 高风险APP行为**（数字足迹反映风险偏好）
- 高风险APP总数: {app_analysis.get('llm_classification', {}).get('high_risk_summary', {}).get('total_high_risk_apps', 'N/A')}个（{app_analysis.get('llm_classification', {}).get('high_risk_summary', {}).get('high_risk_ratio', 0) * 100:.1f}%）
- 类别: 赌博{app_analysis.get('llm_classification', {}).get('high_risk_summary', {}).get('categories', {}).get('gambling', {}).get('count', 'N/A')}个、现金贷{app_analysis.get('llm_classification', {}).get('high_risk_summary', {}).get('categories', {}).get('cash_loan', {}).get('count', 'N/A')}个、金融科技{app_analysis.get('llm_classification', {}).get('high_risk_summary', {}).get('categories', {}).get('fintech_lending', {}).get('count', 'N/A')}个

---

""" + """# 印尼现金贷风控的通用业务逻辑（不随数据变化）

## 5大核心风险模式

### 模式1: 多头借贷 (Co-lending)

**业务逻辑**: 客户在多个平台同时借款 → 资金链断裂 → 必然违约

**可观测信号** (需要设计的特征):
- FDC查询频率激增 (短期vs长期对比)
- 活跃贷款平台数过多
- 在贷余额/收入比值

**特征方向**:
- 查询频率类: 按时间窗口(3/7/30/90d)、按机构类型
- 平台分散度: 活跃平台数、平台集中度
- 借贷强度: 在贷余额、新增贷款速度

---

### 模式2: 高风险偏好 (Risk Appetite)

**业务逻辑**: 安装赌博/克隆/虚拟定位APP → 投机倾向 → 还款意愿低

**可观测信号**:
- 高风险APP安装数量、占比
- 特定类别组合 (赌博+现金贷)
- 近期新增高风险安装

**特征方向**:
- 高风险APP计数、比例
- 类别交叉 (多类别同时安装)
- 新增趋势

---

### 模式3: 收入不稳定 (Income Volatility)

**业务逻辑**: 低收入/无固定工作 → 抗风险能力弱 → 经济波动即违约

**可观测信号**:
- 薪资水平分层
- 职业类型 (固定vs非固定)
- 年龄 (年轻=不稳定)

**特征方向**:
- 收入分层特征
- 职业分类
- 年龄×收入交叉

---

### 模式4: 信用恶化 (Credit Deterioration)

**业务逻辑**: 历史有严重逾期 → 还款意愿/能力有问题 → 再次逾期概率高

**可观测信号**:
- 历史最大逾期天数 (DPD)
- 逾期记录占比
- 近期新增逾期

**特征方向**:
- DPD统计 (最大值、平均值、分位数)
- 逾期历史记录
- 逾期趋势

---

### 模式5: 数字足迹单一 (Digital Footprint Narrow)

**业务逻辑**: 只装借贷APP，没有生活/社交应用 → 可能是新户/欺诈 → 风险高

**可观测信号**:
- APP安装总数过少
- 金融类APP占比过高
- 缺少社交/工作/生活应用

**特征方向**:
- 多样性指数 (熵值、基尼系数)
- 金融占比
- 类别覆盖度

---

## 特征框架设计要求

### 设计原则

1. **覆盖5大风险模式**: 每个模式对应一类特征
2. **参数化模板**: 不是拍脑袋，是系统化组合
3. **不重复现有4710个FDC特征**
4. **质量优先于数量**: IV≥0.05, PSI≤0.2, 覆盖率≥10%
5. **框架稳定**: 后续新增特征在此框架内，不重复设计

### 框架结构

```json
{
  "feature_framework": {
    "meta": {
      "version": "v1.0",
      "design_philosophy": "业务驱动 + 系统化生成",
      "quality_thresholds": {
        "min_iv": 0.05,
        "max_psi": 0.2,
        "min_coverage": 0.10
      }
    },
    "risk_pattern_coverage": {
      "pattern_1_coliding": {"templates": [...], "expected_features": 100},
      "pattern_2_risk_appetite": {"templates": [...], "expected_features": 50},
      "pattern_3_income_instability": {...},
      "pattern_4_credit_deterioration": {...},
      "pattern_5_narrow_footprint": {...}
    },
    "template_categories": [
      {
        "category_name": "类别名称",
        "covered_risk_pattern": "对应的风险模式",
        "business_rationale": "为什么这个类别能捕捉风险",
        "templates": [
          {
            "template_name": "模板名",
            "parameter_space": {"参数名": ["可选值"]},
            "formula_template": "计算逻辑",
            "business_meaning": "这个特征衡量什么",
            "risk_interpretation": "为什么能预测风险",
            "anti_penetration_check": true
          }
        ]
      }
    ]
  }
}
```

## 现有FDC特征 (4710个，必须避免)

主要模式: fdc_all_dpd_* (328个), fdc_all_writeoff_* (328个), fdc_cash_dpd_* (328个)等

---

## 开始

请基于以上业务理解，设计完整的特征框架。重点: **覆盖5大风险模式**，不是凑数量。
"""


if __name__ == '__main__':
    import json
    import pandas as pd

    kb = json.load(open('outputs/knowledge_base/knowledge_base.json', 'r'))
    df = pd.read_excel('FDC4710变量.xlsx')
    fdc_vars = df['Feature Name'].tolist()

    prompt = build_deep_business_prompt(kb, fdc_vars)
    print(f"Prompt长度: {len(prompt)} 字符")
    print(prompt[:800])
