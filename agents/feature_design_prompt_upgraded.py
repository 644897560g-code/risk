"""
特征设计Agent - 升级版Prompt（系统化生成100+特征）

这个文件临时创建，用于测试新的Prompt设计
测试成功后再合并到 feature_design_agent.py
"""

def build_upgraded_prompt(knowledge_base, fdc_variables) -> str:
    """构建升级版的特征设计Prompt"""

    kb = knowledge_base.get('knowledge_base', {})
    summary = kb.get('summary', {})
    base_analysis = kb.get('base_analysis', {})
    app_analysis = kb.get('app_analysis', {})
    fdc_analysis = kb.get('fdc_analysis', {})
    risk_rules = kb.get('risk_rules', [])

    llm_class = app_analysis.get('llm_classification', {})
    high_risk_summary = llm_class.get('high_risk_summary', {})
    category_dist = llm_class.get('category_distribution', {})

    return f"""# 任务：设计印尼现金贷风控**特征框架**（目标：生成100+高质量特征）

## 核心要求（5条，必须遵守）

1. **高质量**: IV>=0.05, PSI<=0.2, 覆盖率>10%
2. **专业深度**: 体现印尼现金贷风控逻辑
3. **可扩展**: 模板化，能生成大量特征
4. **稳定**: 框架确定后不再修改，后续新增特征都在此框架内
5. **可解释**: 业务含义清晰，不强求但尽量有

## 业务背景（必须深度理解）

**客户风险分层**:
- 性别: 男{base_analysis.get('gender_risk', {}).get('male_overdue_rate', 0) * 100:.1f}% vs 女{base_analysis.get('gender_risk', {}).get('female_overdue_rate', 0) * 100:.1f}%（{base_analysis.get('gender_risk', {}).get('risk_ratio', 0):.1f}倍）
- 年龄36-40岁最高风险66.7%，41-50岁最低25%
- 收入与风险负相关（相关系数{base_analysis.get('income_risk_correlation', 'N/A')}）

**高风险APP**（核心信号）:
- 1022个高风险APP（8.6%）：赌博561、现金贷262、金融科技借贷116
- 安装≥2个高风险APP = 严重多头借贷

**FDC信用**（最关键）:
- 查询: 3天4.25次、7天9.4次、30天20.05次
- 贷款: 人均41.6笔、在贷余额809万印尼盾、活跃3.35平台
- 逾期: 平均最大逾期317天、30天+占20%

## 必须设计的7大特征类别

请为每个类别设计**特征模板**，模板包含：
- template_name: 模板名称
- parameter_space: 参数空间（数组形式）
- formula_template: 计算公式模板
- business_rationale: 为什么这个类别重要
- risk_interpretation: 高值预示什么风险
- expected_count: 能生成多少特征

### 类别1: Applist比例特征（~50个）

示例模板：
```yaml
template_name: ratio_applist_category_window
parameter_space:
  categories: [gambling, cash_loan, fintech_lending, banking, ewallet, shopping, ...all 13 categories]
  metrics: [count, ratio, unique_names, recent_install_count]
  windows: [3d, 7d, 30d, 90d]
formula_template: "近{{window}}内{{category}}类别APP的{{metric}} / 总APP数"
business_rationale: "高风险APP安装比例反映客户风险偏好"
risk_interpretation: "比例越高，共债和多头像风险越高"
expected_count: 13 * 4 * 4 = 208
```

### 类别2: Applist多样性特征（~10个）

### 类别3: FDC查询特征（~50个）

### 类别4: FDC贷款特征（~80个）

### 类别5: Base基础特征（~15个）

### 类别6: 交叉特征（~80个）
- Base × Applist: cross_gender_gambling_ratio
- Base × FDC: cross_salary_loan_count
- Applist × FDC: cross_gambling_app_inquiry_count

### 类别7: 时序趋势特征（~50个）
- 短期vs长期: trend_inquiry_3d_vs_30d
- 斜率: slope_loan_count_90d

## 现有FDC特征（必须避免重复）
共{len(fdc_variables)}个，主要模式包括：
- fdc_all_dpd_* (328个)
- fdc_all_writeoff_* (328个)
- fdc_cash_dpd_* (328个)
- ...等

## 输出格式（必须是JSON）

```json
{{
  "feature_framework": {{
    "meta": {{
      "version": "v1.0",
      "design_date": "2026-05-04",
      "target_total": "500+"
    }},
    "template_categories": [
      {{
        "category_name": "applist_ratio",
        "templates": [...],
        "expected_feature_count": 50
      }},
      ... // 7个类别
    ]
  }}
}}
```

## 开始

请输出JSON格式的特征框架（不要有任何前后缀文字）。
"""


if __name__ == '__main__':
    # 测试Prompt构建
    import json
    kb = json.load(open('outputs/knowledge_base/knowledge_base.json', 'r'))
    import pandas as pd
    df = pd.read_excel('FDC4710变量.xlsx')
    fdc_vars = df['Feature Name'].tolist()

    prompt = build_upgraded_prompt(kb, fdc_vars)
    print(f"Prompt长度: {len(prompt)} 字符")
    print(prompt[:500])
