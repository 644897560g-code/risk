"""
完整版特征框架设计 - 12大类别

目标：
1. 覆盖印尼现金贷风控的完整生命周期
2. 基于业务逻辑而非数据快照
3. 框架稳定，后续不频繁调整
"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.llm_client import LLMClient
from agents.legacy.feature_design_deep_prompt_helpers import format_age_risk_dynamic


def analyze_fdc_patterns(fdc_variables: list) -> str:
    """
    分析FDC特征的设计模式

    Args:
        fdc_variables: FDC现有特征变量名列表

    Returns:
        设计模式总结文本
    """
    # 统计分析模式
    patterns = {}
    for var in fdc_variables:
        parts = var.split('_')
        if len(parts) >= 3:
            # 提取模式：fdc_{scope}_{metric}_{window}
            pattern_key = f"{parts[1]}_{parts[2]}"  # all_dpd, cash_loan, etc
            if pattern_key not in patterns:
                patterns[pattern_key] = []
            patterns[pattern_key].append(var)

    summary_lines = [
        f"FDC现有{len(fdc_variables)}个特征，主要设计模式如下：\n"
    ]

    for pattern, vars_list in sorted(patterns.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
        sample_vars = vars_list[:5]
        summary_lines.append(f"- **{pattern}**: {len(vars_list)}个变量")
        summary_lines.append(f"  示例: {', '.join(sample_vars[:3])}")
        parts = pattern.split('_')
        if len(parts) >= 3:
            summary_lines.append(f"  设计思路: {parts[1]}指标的{parts[2]}维度\n")
        else:
            summary_lines.append(f"  设计思路: {pattern}类指标\n")

    return "\n".join(summary_lines)


def build_complete_framework_prompt(knowledge_base: dict, fdc_variables: list) -> str:
    """
    构建12类别的完整特征框架Prompt

    核心思想：
    - 基于印尼现金贷的完整风控逻辑
    - 数据动态传入，不写死
    - 框架稳定，可扩展
    """

    kb = knowledge_base.get('knowledge_base', {})
    summary = kb.get('summary', {})
    base_analysis = kb.get('base_analysis', {})
    app_analysis = kb.get('app_analysis', {})
    fdc_analysis = kb.get('fdc_analysis', {})
    risk_rules = kb.get('risk_rules', [])

    # 分析FDC模式
    fdc_pattern_summary = analyze_fdc_patterns(fdc_variables)

    return f"""# 任务：设计印尼现金贷风控的**完整特征框架体系**（12大类别）

## 业务背景（动态传入）

**样本概况**：
- 样本数：{summary.get('total_samples', 'N/A')}个
- 逾期率：{summary.get('overdue_rate', 0) * 100:.1f}%

**关键风险信号**：
- 性别{base_analysis.get('gender_risk', {}).get('risk_ratio', 0):.1f}倍差异
- {format_age_risk_dynamic(base_analysis.get('age_risk_bins', []))}
- FDC查询：3天{fdc_analysis.get('query_freq_risk', {}).get('last_3days_avg', 'N/A')}次，30天{fdc_analysis.get('query_freq_risk', {}).get('last_30days_avg', 'N/A')}次
- 贷款：人均{fdc_analysis.get('loan_record_stats', {}).get('avg_loan_count', 'N/A')}笔，活跃{fdc_analysis.get('loan_record_stats', {}).get('avg_active_platforms', 'N/A')}平台
- 高风险APP: {app_analysis.get('llm_classification', {}).get('high_risk_summary', {}).get('total_high_risk_apps', 'N/A')}个

## 现有FDC特征设计模式（必须避免重复）

{fdc_pattern_summary}

---

# 印尼现金贷风控的**完整特征生命周期**（12大类别）

基于印尼现金贷业务的**端到端风控逻辑**，特征应该覆盖客户从**申请前→申请中→贷中→贷后**的完整生命周期：

## 类别体系

### 一、客户基础画像（Pre-application）

**1. 客户稳定性特征**
- 业务逻辑：工作/收入/居住的稳定性决定了抗风险能力
- 数据源：base信息
- 关键维度：年龄阶段、职业类型、收入分层、工作年限、婚姻状态、居住稳定性

**2. 数字身份完整性特征**
- 业务逻辑：数字足迹越完整，欺诈风险越低
- 数据源：applist
- 关键维度：APP安装总数、类别覆盖度、生活场景完整性、金融类占比

### 二、申请时行为（Application-time）

**3. 高风险偏好与投机倾向**
- 业务逻辑：安装高风险APP = 风险偏好高 = 还款意愿低
- 数据源：applist
- 关键维度：高风险APP数量、类别交叉、安装动量、风险熵值

**4. 多头借贷与共债压力**
- 业务逻辑：多平台借贷 = 拆东墙补西墙 = 必然违约
- 数据源：FDC
- 关键维度：活跃平台数、在贷余额、查询频率、集中度

### 三、信用历史（Credit History）

**5. 逾期严重度与分布**
- 业务逻辑：历史逾期严重的客户再次逾期概率高
- 数据源：FDC
- 关键维度：最大DPD、逾期比例、DPD分布、严重度指数

**6. 信用恶化趋势**
- 业务逻辑：信用指标随时间恶化 = 即将违约
- 数据源：FDC
- 关键维度：恶化速度、加速度、跨平台传染

**7. 查询行为异常**
- 业务逻辑：短期查询激增 = 资金紧张
- 数据源：FDC
- 关键维度：查询加速度、机构集中度、短期vs长期

### 四、行为模式（Behavioral Patterns）

**8. 贷款行为强度**
- 业务逻辑：贷款频率和金额反映了资金需求的急迫程度
- 数据源：FDC
- 关键维度：贷款笔数趋势、金额分布、新增速度

**9. 应用使用模式**
- 业务逻辑：APP使用时间、更新频率反映用户行为偏好
- 数据源：applist
- 关键维度：安装时长、更新频率、使用时段、活跃度

### 五、综合评估（Holistic）

**10. 收入-负债平衡**
- 业务逻辑：收入无法覆盖负债 = 违约前兆
- 数据源：base × FDC
- 关键维度：收入层级、在贷余额、杠杆比率、偿债能力

**11. 交叉验证一致性**
- 业务逻辑：多维度数据的一致性验证真实性
- 数据源：base × FDC × applist
- 关键维度：申报收入vs借贷规模、年龄vs风险偏好、职业vsAPP类型

**12. 时序演化与生命周期**
- 业务逻辑：客户随时间的变化轨迹
- 数据源：全部数据源的时间窗口对比
- 关键维度：趋势斜率、加速度、周期性、生命周期阶段

---

## 特征设计要求

### 每个类别必须包含

```json
{{
  "category_name": "类别名称",
  "lifecycle_stage": "申请前/申请时/贷中/贷后",
  "business_rationale": "为什么这个类别重要（印尼业务理解）",
  "risk_patterns_covered": ["覆盖的风险模式"],
  "templates": [
    {{
      "template_name": "模板名",
      "parameter_space": {{"参数名": ["可选值列表"]}},
      "formula_template": "计算逻辑",
      "business_meaning": "衡量什么行为",
      "risk_interpretation": "为什么能预测风险",
      "expected_feature_count": 预估数量,
      "anti_penetration": true
    }}
  ],
  "total_expected_features": "该类别预期特征数"
}}
```

### 框架质量要求

1. **覆盖完整性**: 12个类别必须覆盖完整风控生命周期
2. **业务可解释**: 每个特征必须有明确的业务含义
3. **防穿越**: 所有特征只能用申请时刻之前的数据
4. **不重复FDC**: 避免与现有4710个特征重复
5. **质量阈值**: IV≥0.05, PSI≤0.2, 覆盖率≥10%

---

## 输出格式

```json
{{
  "feature_framework": {{
    "meta": {{
      "version": "v1.0",
      "design_date": "2026-05-04",
      "design_philosophy": "完整生命周期覆盖 + 业务驱动",
      "total_categories": 12,
      "quality_thresholds": {{
        "min_iv": 0.05,
        "max_psi": 0.2,
        "min_coverage": 0.10
      }}
    }},
    "lifecycle_coverage": {{
      "pre_application": ["客户稳定性", "数字身份"],
      "application_time": ["高风险偏好", "多头借贷"],
      "credit_history": ["逾期严重度", "恶化趋势", "查询异常"],
      "behavioral": ["贷款行为", "应用模式"],
      "holistic": ["收入负债", "交叉验证", "时序演化"]
    }},
    "template_categories": [
      ...  // 12个类别
    ]
  }}
}}
```

---

## 开始

请基于以上完整框架，设计12大类别的特征体系。重点：**业务逻辑完整**，**框架稳定**，**可扩展**。
"""


def test_complete_framework():
    """测试完整框架生成"""
    print("=" * 70)
    print("生成12类别完整特征框架")
    print("=" * 70)

    # 加载数据
    print("\n1. 加载数据...")
    kb = json.load(open('outputs/knowledge_base/knowledge_base.json', 'r'))
    import pandas as pd
    df = pd.read_excel('FDC4710变量.xlsx')
    fdc_vars = df['Feature Name'].tolist()
    print(f"   样本: {kb['knowledge_base']['summary']['total_samples']}")
    print(f"   FDC变量: {len(fdc_vars)}个")

    # 构建Prompt
    print("\n2. 构建Prompt...")
    prompt = build_complete_framework_prompt(kb, fdc_vars)
    print(f"   长度: {len(prompt)}字符")

    # 调用LLM
    print("\n3. 调用LLM...")
    llm = LLMClient()
    messages = [{"role": "user", "content": prompt}]

    print("   生成中（这可能需要几分钟）...")
    response = llm.chat(messages, temperature=0.3)
    print(f"   ✅ 响应: {len(response)}字符")

    # 提取JSON
    print("\n4. 提取JSON...")
    json_start = response.find('{')
    json_end = response.rfind('}') + 1
    if json_start >= 0:
        json_str = response[json_start:json_end]
        try:
            framework = json.loads(json_str)
            os.makedirs('outputs/feature_design', exist_ok=True)
            output = 'outputs/feature_design/feature_framework_complete_12cats.json'
            with open(output, 'w', encoding='utf-8') as f:
                json.dump(framework, f, ensure_ascii=False, indent=2)
            print(f"   ✅ 保存到: {output}")

            # 统计
            fw = framework.get('feature_framework', {})
            cats = fw.get('template_categories', [])
            print(f"\n5. 框架统计:")
            print(f"   类别数: {len(cats)}")
            for cat in cats:
                templates = len(cat.get('templates', []))
                lifecycle = cat.get('lifecycle_stage', 'N/A')
                expected = cat.get('total_expected_features', 'N/A')
                print(f"   - {cat['category_name']} ({lifecycle}): {templates}模板, 预期{expected}特征")

            print("\n" + "=" * 70)
            print("✅ 完整框架生成成功!")
            print("=" * 70)
            return True

        except json.JSONDecodeError as e:
            print(f"   ❌ JSON失败: {e}")
            return False
    else:
        print("   ❌ 未找到JSON")
        return False


if __name__ == '__main__':
    test_complete_framework()
