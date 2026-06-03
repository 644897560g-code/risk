"""
分步特征框架设计 - Chain of Thought方法（重构版：风险驱动）

重构版本（2026-05-05）:
Step 0: FDC特征预总结（分析4710个特征的设计模式）
第一阶段：风险识别与特征溯源（基于数据分析结果 + FDC摘要 + 应用分类）
第二阶段：特征类别体系设计（按风险类型组织，而非按时间组织）
第三阶段：特征模板生成（含Few-shot，有风险指向标注）
"""

import json
import sys
import os
import re
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.llm_client import LLMClient


def analyze_fdc_naming_patterns(fdc_vars: list) -> dict:
    """
    Step 0: 统计分析FDC特征的命名模式（无需LLM）

    Args:
        fdc_vars: FDC特征名列表

    Returns:
        命名模式统计结果
    """
    patterns = {
        'metric_type': Counter(),
        'time_window': Counter(),
        'data_scope': Counter(),
        'indicator': Counter(),
    }

    for var in fdc_vars:
        parts = var.split('_')

        # 提取指标类型
        if len(parts) >= 3:
            metric = parts[2]  # dpd, cnt, amt, ratio, etc
            patterns['metric_type'][metric] += 1

        # 提取时间窗口
        for part in parts:
            if re.match(r'\d+d', part):  # 3d, 7d, 30d, etc
                patterns['time_window'][part] += 1
            elif part in ['max', 'avg', 'sum', 'min', 'count']:
                patterns['indicator'][part] += 1

        # 提取数据范围
        if len(parts) >= 2:
            scope = parts[1]  # all, cash, card, etc
            patterns['data_scope'][scope] += 1

    return {
        'metric_type': dict(patterns['metric_type'].most_common(20)),
        'time_window': dict(patterns['time_window'].most_common(20)),
        'data_scope': dict(patterns['data_scope'].most_common(10)),
        'indicator': dict(patterns['indicator'].most_common(15)),
    }


def format_pattern_stats(pattern_stats: dict) -> str:
    """
    格式化FDC统计结果供LLM阅读

    Args:
        pattern_stats: analyze_fdc_naming_patterns的输出

    Returns:
        格式化后的统计文本
    """
    lines = []

    lines.append("## 指标类型分布\n")
    for metric, count in pattern_stats['metric_type'].items():
        lines.append(f"- **{metric}**: {count}个特征")

    lines.append("\n## 时间窗口分布\n")
    for window, count in pattern_stats['time_window'].items():
        lines.append(f"- **{window}**: {count}个特征")

    lines.append("\n## 数据范围分布\n")
    for scope, count in pattern_stats['data_scope'].items():
        lines.append(f"- **{scope}**: {count}个特征")

    lines.append("\n## 指标类型分布\n")
    for indicator, count in pattern_stats['indicator'].items():
        lines.append(f"- **{indicator}**: {count}个特征")

    return "\n".join(lines)


def summarize_fdc_patterns(fdc_variables: list) -> dict:
    """
    Step 0: 分析FDC特征的设计模式（先统计，后LLM总结）

    Args:
        fdc_variables: 4710个FDC特征名

    Returns:
        FDC特征分类摘要（~10个风险维度）
    """
    print("   📊 分析FDC命名模式...")
    # 1. 统计分析模式（无需LLM，纯代码）
    pattern_stats = analyze_fdc_naming_patterns(fdc_variables)

    # 2. 用LLM语义化总结（基于统计结果，而非原始4710个特征名）
    prompt = f"""# 任务：总结印尼FDC特征体系的设计逻辑

## FDC特征统计模式
{format_pattern_stats(pattern_stats)}

## 请分析

1. **风险维度分类**：这些特征主要从哪些风险角度设计？
   - 按逾期风险、多头风险、资金饥渴、共债风险等分类
   - 每类特征的设计意图是什么

2. **覆盖程度评估**：
   - 哪些风险被充分覆盖
   - 哪些风险可能存在盲区（如：未持牌平台、APP行为数据等）

3. **设计模式总结**：
   - 特征命名规律（时间窗口、指标类型、数据源）
   - 可复用的模板模式

## 输出JSON格式

```json
{{
  "fdc_summary": {{
    "total_features": {len(fdc_variables)},
    "risk_dimensions": [
      {{
        "dimension_name": "逾期严重度",
        "feature_count": 1493,
        "risk_coverage": "历史逾期记录、违约严重程度",
        "design_intent": "识别有严重逾期史的客户",
        "example_patterns": ["fdc_all_dpd_*", "fdc_cash_dpd_*"],
        "time_windows": ["max", "avg", "sum"],
        "data_source": "KreditBureau Indonesia (SLIK/OJK)"
      }}
    ],
    "coverage_gaps": [
      "FDC不包含未持牌平台",
      "FDC不区分首贷/复贷",
      "FDC不包含APP行为数据"
    ],
    "reusable_templates": [
      "dpd_severity_{{window}}d",
      "inquiry_frequency_{{period}}d",
      "active_platform_count"
    ]
  }}
}}
```

现在请开始分析：
"""

    print("   🤖 LLM正在总结FDC特征设计逻辑...")
    llm = LLMClient()
    response = llm.chat([{"role": "user", "content": prompt}], temperature=0.2)

    # 解析JSON
    json_start = response.find('{')
    json_end = response.rfind('}') + 1
    if json_start >= 0:
        json_str = response[json_start:json_end]
        try:
            fdc_summary = json.loads(json_str)
            print(f"   ✅ FDC总结完成: {len(fdc_summary['fdc_summary']['risk_dimensions'])}个风险维度")
            return fdc_summary
        except json.JSONDecodeError as e:
            print(f"   ⚠️  JSON解析失败: {e}")
            return {}
    else:
        print("   ❌ 未找到JSON")
        return {}


def step1_risk_identification(knowledge_base: dict, fdc_summary: dict) -> dict:
    """
    第一阶段：风险识别与特征溯源（结构化JSON输出）

    Args:
        knowledge_base: 数据分析结果
        fdc_summary: FDC特征摘要（Step 0输出）

    Returns:
        结构化风险清单JSON
    """

    kb = knowledge_base.get('knowledge_base', {})
    summary = kb.get('summary', {})
    base_analysis = kb.get('base_analysis', {})
    app_analysis = kb.get('app_analysis', {})
    fdc_analysis = kb.get('fdc_analysis', {})

    # 提取FDC摘要信息
    fdc_summary_data = fdc_summary.get('fdc_summary', {})
    risk_dimensions = fdc_summary_data.get('risk_dimensions', [])
    coverage_gaps = fdc_summary_data.get('coverage_gaps', [])
    reusable_templates = fdc_summary_data.get('reusable_templates', [])

    # 构建FDC摘要文本
    fdc_summary_text = f"""
## FDC特征设计模式总结

**总特征数**: {fdc_summary_data.get('total_features', 'N/A')}

**风险维度** ({len(risk_dimensions)}个):
"""
    for dim in risk_dimensions[:10]:
        fdc_summary_text += f"- **{dim['dimension_name']}**: {dim.get('feature_count', 'N/A')}个特征，设计意图: {dim.get('design_intent', 'N/A')}\n"

    fdc_summary_text += f"\n**FDC覆盖盲区**:\n"
    for gap in coverage_gaps[:5]:
        fdc_summary_text += f"- {gap}\n"

    fdc_summary_text += f"\n**可复用模板**:\n"
    for tmpl in reusable_templates[:5]:
        fdc_summary_text += f"- {tmpl}\n"

    prompt = f"""# 任务：印尼现金贷风险识别与特征溯源（第一阶段）

## 输入数据分析

### 1. 样本概况
- 样本数：{summary.get('total_samples', 'N/A')}
- 逾期率：{summary.get('overdue_rate', 0) * 100:.1f}%

### 2. 关键风险信号
**客户画像风险**:
- 性别差异: 男性{base_analysis.get('gender_risk', {}).get('male_overdue_rate', 0) * 100:.1f}%，女性{base_analysis.get('gender_risk', {}).get('female_overdue_rate', 0) * 100:.1f}%（{base_analysis.get('gender_risk', {}).get('risk_ratio', 0):.1f}倍）
- 年龄模式: 需结合业务逻辑分析

**多头借贷**:
- FDC查询: 3天{fdc_analysis.get('query_freq_risk', {}).get('last_3days_avg', 'N/A')}次，30天{fdc_analysis.get('query_freq_risk', {}).get('last_30days_avg', 'N/A')}次
- 活跃平台: {fdc_analysis.get('loan_record_stats', {}).get('avg_active_platforms', 'N/A')}个

**高风险APP行为**:
- 高风险APP总数: {app_analysis.get('llm_classification', {}).get('high_risk_summary', {}).get('total_high_risk_apps', 'N/A')}个

### 3. 现有FDC特征设计模式

{fdc_summary_text}

---

## 核心问题：请回答以下3个问题

### 问题1：印尼现金贷的主要风险分类有哪些？

请列出**5-8个核心风险类型**，每个包含：
- **risk_type**: 英文标识（如 co-lending, risk-appetite）
- **risk_name_cn**: 中文名称
- **description**: 业务逻辑描述
- **prevalence**: 在当前样本中的普遍程度（估计占比）

### 问题2：每类风险的典型客户画像是什么？

对每个风险类型，描述：
- **typical_profiles**: 2-3个典型画像
  - profile_id: 画像ID
  - description: 画像描述
  - overdue_rate: 预估逾期率
  - key_signals: 关键识别信号

### 问题3：通过哪些数据可以识别这些风险？

对每个风险类型，明确指出：
- **data_sources**: 需要的数据源（base/applist/fdc）
- **identifiable_signals**: 可观测的信号列表
- **fdc_coverage_analysis**:
  - fdc_covers_this_risk: FDC是否已覆盖此风险
  - coverage_level: 覆盖程度（高/中/低/无）
  - existing_fdc_patterns: FDC已有的相关特征模式（从上面FDC摘要中提取）
  - fdc_gaps: FDC的覆盖盲区
  - new_feature_opportunity: 新特征机会点

---

## 输出格式

请输出**严格JSON格式**（不要有其他文字）：

```json
{{
  "phase1_risk_identification": {{
    "total_risk_types": 6,
    "risk_patterns": [
      {{
        "risk_type": "co-lending",
        "risk_name_cn": "多头借贷",
        "description": "客户在多个平台同时借款，资金链断裂风险",
        "prevalence_in_sample": "约45%的逾期由此引起",
        "typical_profiles": [
          {{
            "profile_id": "co-lending_intensive",
            "description": "同时装5+个现金贷APP，近7天FDC查询>10次",
            "overdue_rate": "约80%",
            "key_signals": ["loan_app_density > 15%", "fdc_query_velocity_7d > 10"]
          }}
        ],
        "data_sources": ["applist", "fdc"],
        "identifiable_signals": ["loan_app_density > 15%", "fdc_query_velocity_7d > 10"],
        "fdc_coverage_analysis": {{
          "fdc_covers_this_risk": true,
          "coverage_level": "高",
          "existing_fdc_patterns": ["fdc_all_cnt_*", "fdc_all_outstanding_*"],
          "fdc_gaps": ["FDC不包含未持牌平台", "FDC不区分首贷/复贷"],
          "new_feature_opportunity": ["结合applist补充FDC盲区", "识别马甲包/聚合器进件"]
        }}
      }}
    ]
  }}
}}
```

现在请开始分析：
"""

    llm = LLMClient()
    response = llm.chat([{"role": "user", "content": prompt}], temperature=0.3)

    # 解析JSON
    json_start = response.find('{')
    json_end = response.rfind('}') + 1
    if json_start >= 0:
        json_str = response[json_start:json_end]
        try:
            result = json.loads(json_str)
            return result
        except json.JSONDecodeError as e:
            print(f"   ⚠️  JSON解析失败: {e}")
            return {}
    else:
        print("   ❌ 未找到JSON")
        return {}


def step2_category_design(phase1_result: dict, knowledge_base: dict) -> dict:
    """
    第二阶段：特征类别体系设计（基于风险清单）

    Args:
        phase1_result: 第一阶段输出的风险清单JSON
        knowledge_base: 数据分析结果

    Returns:
        特征类别体系JSON
    """
    kb = knowledge_base.get('knowledge_base', {})

    # 提取风险模式
    risk_patterns = phase1_result.get('phase1_risk_identification', {}).get('risk_patterns', [])

    # 构建风险摘要文本
    risk_summary_text = ""
    for rp in risk_patterns:
        risk_summary_text += f"""
### {rp['risk_name_cn']} ({rp['risk_type']})
- **描述**: {rp['description']}
- **普遍程度**: {rp['prevalence_in_sample']}
- **典型画像**: {len(rp.get('typical_profiles', []))}个
- **数据源**: {', '.join(rp.get('data_sources', []))}
- **FDC覆盖**: {rp.get('fdc_coverage_analysis', {}).get('coverage_level', 'N/A')}
"""

    prompt = f"""# 任务：基于风险清单设计特征类别体系（第二阶段）

## 输入：第一阶段风险识别结果

{risk_summary_text}

## 设计要求

请基于以上6个风险类型，设计**特征类别体系**，满足：

### 核心原则

1. **风险驱动**: 每个类别必须明确对应1-2个风险类型
2. **覆盖完整**: 所有6个风险类型都必须被类别覆盖
3. **业务可解释**: 每个类别有明确的业务含义和数据源
4. **可扩展性**: 类别下可生成多个模板（参数化组合）

### 每个类别必须包含

```json
{{
  "category_name": "类别名称（英文蛇形）",
  "category_name_cn": "类别名称（中文）",
  "covered_risk_types": ["risk_type_1", "risk_type_2"],
  "business_rationale": "为什么这个类别重要（结合印尼业务）",
  "data_sources": ["applist", "fdc", "base"],
  "design_principles": ["原则1", "原则2"],
  "expected_template_count": 2-3
}}
```

### 类别覆盖要求

至少覆盖以下维度（基于6个风险类型）：
1. **多头借贷识别** (multi_lending) → 1-2个类别
2. **欺诈防范** (fraud_synthetic) → 1-2个类别
3. **债务监控** (debt_spiral) → 1-2个类别
4. **风险偏好** (risk_appetite) → 1个类别
5. **收入稳定性** (income_instability) → 1个类别
6. **行为演化** (evasion_behavior) → 1个类别

总计预计 **8-12个类别**。

## 输出格式

请输出**严格JSON格式**：

```json
{{
  "phase2_category_system": {{
    "total_categories": 10,
    "categories": [
      {{
        "category_name": "loan_app_density_features",
        "category_name_cn": "贷款APP密度特征",
        "covered_risk_types": ["multi_lending", "debt_spiral"],
        "business_rationale": "印尼现金贷用户常在多个平台同时借款，贷款类APP安装密度直接反映多头借贷倾向",
        "data_sources": ["applist"],
        "design_principles": [
          "区分持牌机构与未持牌平台",
          "结合安装时间和更新频率",
          "计算密度=贷款APP数/总安装数"
        ],
        "expected_template_count": 3
      }}
    ]
  }}
}}
```

现在请开始设计：
"""

    llm = LLMClient()
    response = llm.chat([{"role": "user", "content": prompt}], temperature=0.3)

    # 解析JSON
    json_start = response.find('{')
    json_end = response.rfind('}') + 1
    if json_start >= 0:
        json_str = response[json_start:json_end]
        try:
            result = json.loads(json_str)
            return result
        except json.JSONDecodeError as e:
            print(f"   ⚠️  JSON解析失败: {e}")
            return {}
    else:
        print("   ❌ 未找到JSON")
        return {}


def step3_template_generation(phase2_result: dict, phase1_result: dict) -> dict:
    """
    第三阶段：特征模板生成（有风险指向，含数据字典约束）

    Args:
        phase2_result: 第二阶段输出的类别体系JSON
        phase1_result: 第一阶段输出的风险清单JSON

    Returns:
        特征模板系统JSON
    """
    categories = phase2_result.get('phase2_category_system', {}).get('categories', [])

    # FDC字段分布数据（基于2094个样本，117,026条贷款记录的统计分析）
    FDC_DATA_DICT = """
## ⚠️ 强制约束：FDC真实字段和枚举值（基于**2094个样本**，**117,026条贷款记录**统计，必须遵守）

### 1. FDC - pinjaman（贷款记录）字段

**status_pinjaman** (贷款状态代码):
- ✅ 可用值: `["L", "O", "W", "R", "F", "X", "S"]`
  - L = Fully Paid (已结清，96,144条/82.2%)
  - O = Outstanding (未结清，12,844条/11.0%)
  - W = Write-Off (核销，6,176条/5.3%)
  - R = Restructure (重组，867条/0.7%)
  - F = Full Payment (全额还款，730条/0.6%)
  - X = Deferred Loan (延期贷款，167条/0.1%)
  - S = Partial Payment (部分还款，98条/0.1%)
- ❌ 不能使用: approved, rejected, pending (这些状态不存在)

**status_pinjaman_ket** (贷款状态描述):
- ✅ 可用值: `["Fully Paid", "Outstanding", "Write-Off", "Restructure", "Full Payment", "Deferred Loan", "Partial Payment"]`

**kualitas_pinjaman** (贷款质量代码):
- ✅ 可用值: `["1", "2", "5", "4", "3"]`
  - 1 = Lancar (正常，98,142条/83.9%)
  - 2 = Dalam Perhatian Khusus (关注，10,154条/8.7%)
  - 5 = Macet (呆账，6,385条/5.5%)
  - 4 = Diragukan (可疑，1,376条/1.2%)
  - 3 = Kurang Lancar (次正常，969条/0.8%)
- ❌ 不能使用: good, bad, normal 等简化分类

**kualitas_pinjaman_ket** (贷款质量描述):
- ✅ 可用值: `["Lancar", "Dalam Perhatian Khusus", "Macet", "Diragukan", "Kurang Lancar"]`

**penyelesaian_w_oleh** (违约解决方式):
- ✅ 可用值: `["Default", "Insurance", "Desk Collection", "Other"]`
  - Default: 112,908条 (96.5%)
  - Insurance: 3,295条 (2.8%)
  - Desk Collection: 704条 (0.6%)
  - Other: 119条 (0.1%)

**tipe_pinjaman** (贷款类型):
- ✅ 可用值: `["Multiguna", "Produktif"]`
  - Multiguna (多用途): 108,119条 (92.4%)
  - Produktif (生产性): 8,907条 (7.6%)

**sub_tipe_pinjaman** (子贷款类型):
- ✅ 可用值 (Top 10):
  - Onetime Loan / Cash Loan: 84,916条 (72.6%)
  - Paylater/ Line Of Credit: 21,418条 (18.3%)
  - Online-Merchant Financing: 5,875条 (5.0%)
  - Others: 1,600条 (1.4%)
  - Default: 1,537条 (1.3%)
  - Working Capital: 905条 (0.8%)
  - Offline Buyer/Inventory Financing: 290条 (0.2%)
  - Ijarah: 248条 (0.2%)
  - Education Financing: 121条 (0.1%)
  - Invoice Financing: 81条 (0.1%)

**pendanaan_syariah** (是否伊斯兰金融):
- ✅ 可用值: `["False", "True"]` (字符串,不是数字)
  - False (非伊斯兰金融): 116,778条 (99.8%)
  - True (伊斯兰金融): 248条 (0.2%)
- 类型: Boolean (true/false字符串)

**jenis_pengguna** (用户类型代码):
- ✅ 可用值: `[1]` (100%，Individual个人用户)

**jenis_pengguna_ket** (用户类型描述):
- ✅ 可用值: `["Individual", "Company"]`
  - Individual: 117,025条
  - Company: 1条

**dpd_max** (最大逾期天数):
- ✅ 范围: 0 - 2858天
- ✅ 均值: 85.11天
- ✅ 分布:
  - DPD=0 (无逾期): 79,486条 (67.9%)
  - DPD>0 (有逾期): 37,540条 (32.1%)
- ✅ 类型: Integer

**其他可用字段**:
- `id_penyelenggara`: 机构ID (97个唯一值)
  - Top 10机构:
    - AFDC239: 15,991条
    - AFDC123: 15,427条
    - AFDC233: 14,307条
    - AFDC168: 10,023条
    - AFDC243: 5,981条
    - AFDC130: 5,566条
    - AFDC150: 4,233条
    - AFDC161: 2,978条
    - AFDC230: 2,921条
    - AFDC106: 2,899条
- `nilai_pendanaan`: 借款金额 (IDR印尼盾)
- `tgl_penyaluran_dana`: 放款日期 (YYYY-MM-DD格式)
- `tgl_jatuh_tempo_pinjaman`: 到期日
- `sisa_pinjaman_berjalan`: 未结清余额
- `dpd_terakhir`: 最后逾期天数
- `pendapatan`: 收入
- `agunan`: 抵押品
- `tipe_pinjaman`: 贷款类型

### 2. FDC - history_inquiry（查询历史）字段

**statistic** (查询统计):
- `3_hari`: 近3天查询次数
- `7_hari`: 近7天查询次数
- `30_hari`: 近30天查询次数
- `90_hari`: 近90天查询次数
- `180_hari`: 近180天查询次数
- `360_hari`: 近360天查询次数
- `>360_hari`: 超过360天查询次数

**last3DaysInquiry** (近3天查询明细):
- `hit_by`: 查询机构名 (如 KREDINESIA, KLIKUMKM, FINPLUS)
- `jml_data`: 数据条数
- `tgl_inquiry`: 查询时间

### 3. applist（应用列表）字段

**可用字段**:
- `inTime`: 安装时间戳 (毫秒)
- `upTime`: 更新时间戳 (毫秒)
- `packageX`: 包名 (如 "co.id.lumbungdana.android")
- `appName`: 应用名称 (如 "Lumbung Dana")
- `versionName`: 版本号 (如 "1.3.15")

**❌ 不存在的字段**:
- `install_source`: applist中无安装来源字段
- `app_category`: applist中无预设分类，需使用16个标准类别映射

### ⚠️ **重要：完整字段白名单（只能使用以下字段）**

```
✅ base可用字段: applyTime, birthday, job, salary, workYears, marita, children,
                  channel, appname, idCard, gaid
   (注意: gender已废弃,从idCard第7-8位推导)

✅ applist可用字段: inTime, upTime, packageX, appName, versionName

✅ FDC - pinjaman可用字段:
   status_pinjaman, status_pinjaman_ket, kualitas_pinjaman, kualitas_pinjaman_ket,
   tipe_pinjaman, sub_tipe_pinjaman, pendanaan_syariah, dpd_max, id_penyelenggara,
   nilai_pendanaan, tgl_penyaluran_dana, tgl_jatuh_tempo_pinjaman,
   sisa_pinjaman_berjalan, dpd_terakhir, pendapatan, agunan, penyelesaian_w_oleh

✅ FDC - history_inquiry可用字段:
   3_hari, 7_hari, 30_hari, 90_hari, 180_hari, 360_hari, >360_hari,
   last3DaysInquiry.hit_by, last3DaysInquiry.jml_data, last3DaysInquiry.tgl_inquiry
```

### 🚫 **严格禁止捏造以下不存在的字段** (发现立即拒绝)
```
❌ device_ip, base_station, cell_tower, wifi_name (无地理位置数据)
❌ screen_resolution, os_version, cpu_model, battery_health, storage_usage (无设备详情)
❌ device_id, imei, android_id, mac_address (只有gaid可用)
❌ cache_clear, system_log, activity_log (无系统日志)
❌ shipping_address, phone_prefix, shared_contacts, emergency_contact (无联系人数据)
❌ user_id, session_id (无此类标识符)
```

**可用APP分类** (16个离线分类类别 - **动态加载，不要写死**):
- 这些类别来自 offline_app_classification 任务
- 具体类别列表在运行时从 classification_complete_XXXXX.json 读取
- 在模板中应该标注: "使用16个标准APP分类"（具体类别由特征工程Agent从缓存加载）
- ❌ 不要编造不在16个分类中的类别（如 p2p_lending, instant_loan, payday_loan 等）

### 4. base（基础信息）字段

**可用字段**:
- `applyTime`: 申请时间戳 (毫秒)
- `birthday`: 生日 (DD-MM-YYYY格式)
- `job`: 职业类别代码 (如 "12")
- `gender`: ⚠️ **废弃字段** - 与身份证号推导的性别不一致率高达84.6%
- **正确的性别获取方法**: 从 `idCard` 字段第7-12位推导
  ```python
  def extract_gender_from_idcard(id_card: str) -> int:
      day_code = int(id_card[6:8])  # 第7-8位
      if 1 <= day_code <= 31: return 0  # 男性
      elif 41 <= day_code <= 71: return 1  # 女性 (需减40)
  ```
- **真实性别分布** (基于2104个样本): 男性71.2%, 女性28.8%
- `salary`: 月收入 (IDR印尼盾)
- `workYears`: 工作年限
- `marita`: 婚姻状态
- `children`: 子女数
- `channel`: 渠道
- `appname`: 应用名称 (flex-rupiah, dll)

### 5. 机构分类说明

**已知机构ID示例** (基于25个样本):
AFDC241, AFDC253, AFDC229, AFDC183, AFDC233, AFDC220, AFDC255, AFDC248, AFDC246, AFDC209, AFDC217, AFDC133, AFDC215, AFDC165, AFDC198

**如需分类机构** (bank/licensed_fintech/unlicensed_pinjol):
- 必须在模板中标注: "需要配置 id_penyelenggara 映射表"
- 或基于已知ID定义规则，如:
  - bank: 包含"bank"的机构名或特定ID段
  - licensed_fintech: OJK持牌机构
  - unlicensed_pinjol: 未持牌网贷平台

## ⚠️ 模板生成强制规则（必须遵守，违反=拒绝）

1. **parameter_space 中的值必须来自上述枚举值**
   - ✅ 正确: `"status_types": ["O", "L"]`
   - ❌ 错误: `"status_types": ["approved", "rejected", "pending"]`

2. **🚨 严格禁止捏造任何不存在的字段 (LLM反幻觉红线)**
   - **唯一可用字段清单** (见上方"完整字段白名单"):
     - base: applyTime, birthday, job, salary, workYears, marita, children, channel, appname, idCard, gaid
     - applist: inTime, upTime, packageX, appName, versionName
     - FDC pinjaman: status_pinjaman, kualitas_pinjaman, dpd_max, id_penyelenggara, nilai_pendanaan, tgl_penyaluran_dana, ...
     - FDC inquiry: 3_hari, 7_hari, last3DaysInquiry.hit_by, ...
   - **❌ 绝对禁止使用以下字段** (这些都不存在):
     - device_ip, base_station, cell_tower, screen_resolution, os_version, cpu_model, battery_health, storage_usage
     - device_id, imei, android_id, mac_address (只用gaid)
     - cache_clear, system_log, activity_log, user_id, session_id
     - shipping_address, phone_prefix, shared_contacts, emergency_contact
   - **✅ 正确做法**: 只使用白名单中的字段设计公式
   - **🚫 违规检测**: 如发现捏造字段，模板立即拒绝并标注"LLM hallucination"

3. **不能使用不存在的字段**
   - ❌ 不能用: `install_source` (applist里没有)
   - ✅ 可以用: `inTime`, `upTime`, `packageX`, `appName`

4. **APP类别必须使用16个标准类别（但不要写死具体值）**
   - ❌ 不能编造类别: `p2p_lending`, `instant_loan`, `payday_loan`
   - ✅ 在模板中标注: "使用16个标准APP分类，具体类别由特征工程Agent从 classification_complete_XXXXX.json 加载"
   - ✅ 示例类别（仅供参考）: `cash_loan`, `fintech_lending`, `banking`, `ewallet`, `gambling` 等

5. **机构分类需要标注规则需求**
   - 如果模板需要区分 bank/licensed_fintech/unlicensed_pinjol
   - 必须在模板中标注: "需要配置 id_penyelenggara 映射表"

6. **性别字段必须从idCard推导，不要使用base.gender**
   - ❌ 不能用: `base.gender` (84.6%的样本错误)
   - ✅ 正确做法: 在模板中标注 "通过idCard第7-12位推导性别"
   - 示例: `gender = extract_gender_from_idcard(idCard)` (day_code 1-31=男, 41-71=女)
"""

    # 构建Few-shot示例（使用真实字段）
    few_shot_examples = """
## Few-shot示例（基于真实数据字段的高质量模板）

### 示例1: 多头借贷FDC查询集中度
```json
{{
  "template_name": "fdc_inquiry_concentration_index",
  "parameter_space": {{
    "short_windows": ["3d", "7d"],
    "long_windows": ["30d", "90d"],
    "status_types": ["O"]  // 注意：使用真实状态 O=Outstanding
  }},
  "formula_template": "COUNT(status_pinjaman='O' AND tgl_penyaluran_dana∈近{{short_window}}) / COUNT(history_inquiry.last3DaysInquiry)",
  "business_meaning": "未结清贷款在短期内的集中度，反映紧急资金需求。印尼市场多头借贷者常在多平台同时保持未结清贷款。",
  "risk_interpretation": "近7天未结清贷款占比>40%且短期窗口≤3d，表明资金链极度紧绷，M1+违约率提升3.2倍。",
  "covered_risk_types": ["multi_lending"],
  "expected_feature_count": 4,
  "anti_penetration": true
}}
```

### 示例2: 贷款APP安装速度
```json
{{
  "template_name": "loan_app_installation_velocity",
  "parameter_space": {{
    "velocity_windows": ["24h", "72h", "7d"],
    "app_categories": ["cash_loan", "fintech_lending"],  // 注意：使用16个标准类别
    "inTime_thresholds": [1, 3, 5]
  }},
  "formula_template": "COUNT(inTime∈近{{velocity_window}}且appName匹配{{app_categories}}的APP数)",
  "business_meaning": "短期密集安装贷款APP的速度，印尼黑产中介常引导用户批量安装贷款APP以快速套现。",
  "risk_interpretation": "72h内安装≥3个cash_loan类APP，欺诈进件概率>60%，直接拦截。",
  "covered_risk_types": ["multi_lending", "illegal_pinjol_trap"],
  "expected_feature_count": 6,
  "anti_penetration": true
}}
```

### 示例3: DPD严重度趋势
```json
{{
  "template_name": "dpd_severity_trend_score",
  "parameter_space": {{
    "quality_codes": ["1", "2"],  // 注意：使用真实kualitas_pinjaman
    "status_filter": ["O"],       // 仅统计未结清贷款
    "trend_windows": ["30d", "90d"]
  }},
  "formula_template": "SUM(dpd_max WHERE kualitas_pinjaman='2' AND status_pinjaman='O' AND tgl_penyaluran_dana∈近{{trend_window}}) / COUNT(...)",
  "business_meaning": "关注类贷款的DPD趋势，印尼市场DPD>5即表明还款意愿薄弱。",
  "risk_interpretation": "DPD均值>2且kualitas_pinjaman='2'占比>10%，违约概率>75%。",
  "covered_risk_types": ["debt_spiral"],
  "expected_feature_count": 4,
  "anti_penetration": true
}}
```
"""

    # 构建类别摘要
    category_summary = ""
    for cat in categories:
        category_summary += f"""
### {cat['category_name']} ({cat['category_name_cn']})
- **对应风险**: {', '.join(cat.get('covered_risk_types', []))}
- **数据源**: {', '.join(cat.get('data_sources', []))}
- **业务依据**: {cat.get('business_rationale', '')[:150]}
- **预期模板数**: {cat.get('expected_template_count', 2)}个
"""

    prompt = f"""# 任务：为每个特征类别生成具体模板（第三阶段）

## ⚠️ 重要：必须先阅读数据字典约束

在生成模板前，请仔细阅读以下数据字典，**所有参数值必须基于真实字段**：

{FDC_DATA_DICT}

## 输入：第二阶段类别体系

{category_summary}

## 设计要求

### 为每个类别生成2-3个特征模板

要求：
1. **template_name**: 英文蛇形命名，清晰表达业务含义
2. **parameter_space**: 详细的参数空间（JSON对象，3-5个维度）**必须使用上述字典中的枚举值**
3. **formula_template**: 计算逻辑模板（支持参数替换，使用真实字段名）
4. **business_meaning**: 这个特征衡量什么行为（中文）
5. **risk_interpretation**: 为什么能预测风险（**必须包含量化阈值**）
6. **covered_risk_types**: 明确标注覆盖的风险类型（从第一阶段继承）
7. **expected_feature_count**: 预期生成的特征数
8. **anti_penetration**: 是否符合防穿越原则

### 模板质量要求

参考Few-shot示例的质量：
- **参数空间必须具体**：必须使用上述字典中的真实枚举值
- **业务解释必须深入**：不仅说"是什么"，还要说"为什么有效"（结合印尼业务）
- **风险解释必须量化**：给出阈值，如"密度>15%表明..."
- **风险指向必须明确**：标注覆盖的风险类型

## 输出格式

请输出**严格JSON格式**：

```json
{{
  "phase3_template_system": {{
    "total_templates": 24,
    "categories_with_templates": [
      {{
        "category_name": "loan_app_density_features",
        "templates": [
          {{
            "template_name": "loan_app_density_ratio",
            "parameter_space": {{...}},
            "formula_template": "...",
            "business_meaning": "...",
            "risk_interpretation": "...",
            "covered_risk_types": ["multi_lending", "debt_spiral"],
            "expected_feature_count": 9,
            "anti_penetration": true
          }}
        ]
      }}
    ]
  }}
}}
```

{few_shot_examples}

现在请开始为{len(categories)}个类别生成模板：
"""

    llm = LLMClient()
    response = llm.chat([{"role": "user", "content": prompt}], temperature=0.3)

    # 解析JSON
    json_start = response.find('{')
    json_end = response.rfind('}') + 1
    if json_start >= 0:
        json_str = response[json_start:json_end]
        try:
            result = json.loads(json_str)
            return result
        except json.JSONDecodeError as e:
            print(f"   ⚠️  JSON解析失败: {e}")
            return {}
    else:
        print("   ❌ 未找到JSON")
        return {}


def execute_stepwise_design():
    """
    执行重构后的分步设计流程（风险驱动版本）

    流程:
    Step 0: FDC特征预总结
    第一阶段: 风险识别与特征溯源
    第二阶段: 特征类别体系设计（基于风险清单）
    第三阶段: 特征模板生成（有风险指向）
    """

    print("=" * 70)
    print("分步特征框架设计 - 风险驱动版本（重构）")
    print("=" * 70)

    # 加载数据
    print("\n1. 加载数据...")
    kb = json.load(open('outputs/knowledge_base/knowledge_base.json', 'r'))
    import pandas as pd
    df = pd.read_excel('FDC4710变量.xlsx')
    fdc_vars = df['Feature Name'].tolist()
    print(f"   样本: {kb['knowledge_base']['summary']['total_samples']}")
    print(f"   FDC变量: {len(fdc_vars)}个")

    # ========== Step 0: FDC特征预总结 ==========
    print("\n" + "=" * 70)
    print("Step 0: FDC特征预总结")
    print("=" * 70)

    print("\n📊 统计分析FDC命名模式...")
    fdc_summary = summarize_fdc_patterns(fdc_vars)

    if not fdc_summary:
        print("   ❌ FDC总结失败，流程终止")
        return

    # 保存Step 0结果
    os.makedirs('outputs/feature_design/stepwise', exist_ok=True)
    with open('outputs/feature_design/stepwise/step0_fdc_summary.json', 'w', encoding='utf-8') as f:
        json.dump(fdc_summary, f, ensure_ascii=False, indent=2)
    print("   💾 保存到: step0_fdc_summary.json")

    # ========== 第一阶段: 风险识别与特征溯源 ==========
    print("\n" + "=" * 70)
    print("第一阶段: 风险识别与特征溯源")
    print("=" * 70)

    print("\n🤖 LLM正在识别风险模式...")
    phase1_result = step1_risk_identification(kb, fdc_summary)

    if not phase1_result:
        print("   ❌ 风险识别失败，流程终止")
        return

    print(f"✅ 风险识别完成，识别 {len(phase1_result.get('phase1_risk_identification', {}).get('risk_patterns', []))} 个风险类型")

    # 保存第一阶段结果
    with open('outputs/feature_design/stepwise/phase1_risk_identification.json', 'w', encoding='utf-8') as f:
        json.dump(phase1_result, f, ensure_ascii=False, indent=2)
    print("   💾 保存到: phase1_risk_identification.json")

    # ========== 第二阶段: 特征类别体系设计 ==========
    print("\n" + "=" * 70)
    print("第二阶段: 特征类别体系设计（基于风险清单）")
    print("=" * 70)

    print("\n🤖 LLM正在设计特征类别...")
    phase2_result = step2_category_design(phase1_result, kb)

    if not phase2_result:
        print("   ❌ 类别设计失败，流程终止")
        return

    cats = phase2_result.get('phase2_category_system', {}).get('categories', [])
    print(f"✅ 类别设计完成，设计了 {len(cats)} 个特征类别")

    # 保存第二阶段结果
    with open('outputs/feature_design/stepwise/phase2_category_system.json', 'w', encoding='utf-8') as f:
        json.dump(phase2_result, f, ensure_ascii=False, indent=2)
    print("   💾 保存到: phase2_category_system.json")

    # 打印类别摘要
    print("\n📊 特征类别分布:")
    for cat in cats:
        risk_types = ', '.join(cat.get('covered_risk_types', []))
        print(f"   - {cat['category_name_cn']} ({cat['category_name']}): 覆盖风险 [{risk_types}]")

    # ========== 第三阶段: 特征模板生成 ==========
    print("\n" + "=" * 70)
    print("第三阶段: 特征模板生成（有风险指向）")
    print("=" * 70)

    print("\n🤖 LLM正在生成特征模板...")
    phase3_result = step3_template_generation(phase2_result, phase1_result)

    if not phase3_result:
        print("   ❌ 模板生成失败，流程终止")
        return

    templates = phase3_result.get('phase3_template_system', {}).get('categories_with_templates', [])
    total_templates = sum(len(t['templates']) for t in templates)
    print(f"✅ 模板生成完成，共 {len(templates)} 个类别, {total_templates} 个模板")

    # 保存第三阶段结果
    with open('outputs/feature_design/stepwise/phase3_template_system.json', 'w', encoding='utf-8') as f:
        json.dump(phase3_result, f, ensure_ascii=False, indent=2)
    print("   💾 保存到: phase3_template_system.json")

    # 打印模板摘要
    print("\n📊 模板分布:")
    for cat in templates:
        template_count = len(cat['templates'])
        print(f"   - {cat['category_name']}: {template_count}个模板")

    print("\n" + "=" * 70)
    print("✅ 三阶段框架设计全部完成!")
    print("=" * 70)
    print("\n输出文件:")
    print("  1. step0_fdc_summary.json - FDC特征预总结")
    print("  2. phase1_risk_identification.json - 风险识别清单")
    print("  3. phase2_category_system.json - 特征类别体系")
    print("  4. phase3_template_system.json - 特征模板系统")
    print("\n下一步: 基于模板生成具体特征列表（自动化展开）")


def expand_templates_to_features():
    """
    展开 phase3_template_system.json 中的24个模板为具体特征列表，
    生成特征工程Agent可读的 feature_design_doc.json

    用LLM展开模板参数空间，生成具体特征名、类型、计算逻辑等。
    """
    print("\n" + "=" * 70)
    print("展开模板为具体特征列表")
    print("=" * 70)

    # 1. 加载模板
    template_path = 'outputs/feature_design/stepwise/phase3_template_system.json'
    if not os.path.exists(template_path):
        print(f"  ❌ 找不到模板文件: {template_path}")
        return False

    with open(template_path, 'r', encoding='utf-8') as f:
        template_data = json.load(f)

    categories = template_data.get('phase3_template_system', {}).get('categories_with_templates', [])
    total_templates = sum(len(c['templates']) for c in categories)
    print(f"  加载 {len(categories)} 个类别, {total_templates} 个模板")

    # 2. 加载FDC变量用于去重
    import pandas as pd
    fdc_path = 'FDC4710变量.xlsx'
    fdc_names = set()
    if os.path.exists(fdc_path):
        df = pd.read_excel(fdc_path)
        fdc_names = set(df['Feature Name'].tolist())
        print(f"  加载 {len(fdc_names)} 个FDC变量用于去重")

    # 3. 用LLM展开模板（增大max_tokens确保完整输出）
    llm = LLMClient()
    prompt = _build_expand_prompt(categories, total_templates, fdc_names)
    print(f"  🤖 LLM正在展开模板...")
    response = llm.chat([{"role": "user", "content": prompt}], temperature=0.2, max_tokens=16000)

    # 解析JSON - 增强容错
    # 先去掉markdown代码块标记
    cleaned = response.strip()
    if cleaned.startswith('```'):
        cleaned = cleaned[cleaned.index('\n') + 1:]
    if cleaned.endswith('```'):
        cleaned = cleaned[:cleaned.rfind('```')]
    cleaned = cleaned.strip()

    json_start = cleaned.find('{')
    json_end = cleaned.rfind('}') + 1
    if json_start < 0:
        print(f"  ❌ 无法从响应中提取JSON")
        with open('outputs/feature_design/stepwise/expand_raw_response.txt', 'w', encoding='utf-8') as f:
            f.write(response)
        print(f"  💾 原始响应已保存到 expand_raw_response.txt")
        return False

    json_str = cleaned[json_start:json_end]

    # 尝试多种JSON解析方式
    result = None
    # 方式1: 标准解析
    import re as _re
    try:
        result = json.loads(json_str)
    except json.JSONDecodeError:
        # 方式2: 先尝试修复截断问题（如果不是JSON数组而是对象，找到完整的末尾）
        try:
            # 查找最后一个完整的 "key": value 对
            last_brace = json_str.rfind('}')
            # 移除截断的字段
            import re as _re2
            # 尝试修复尾随逗号和截断
            fixed = _re2.sub(r',\s*\}', '}', json_str)
            fixed = _re2.sub(r',\s*\]', ']', fixed)
            result = json.loads(fixed)
        except json.JSONDecodeError:
            pass

    if result is None:
        print(f"  ❌ JSON解析失败，尝试保存原始响应")
        with open('outputs/feature_design/stepwise/expand_raw_response.txt', 'w', encoding='utf-8') as f:
            f.write(response)
        print(f"  💾 原始响应已保存到 expand_raw_response.txt")
        return False

    features = result.get('features', [])
    if not features:
        print(f"  ❌ 未生成任何特征")
        return False

    # 4. 去重检查
    unique_features = []
    seen_names = set()
    for f in features:
        name = f.get('feature_name', '')
        if name and name not in seen_names and name not in fdc_names:
            unique_features.append(f)
            seen_names.add(name)

    dedup_count = len(features) - len(unique_features)
    print(f"  展开后: {len(features)} 个特征, 去重 {dedup_count} 个, 保留 {len(unique_features)} 个")

    # 5. 保存
    output = {
        'feature_design_version': '3.0',
        'design_method': 'risk_driven_stepwise',
        'description': '三阶段风险驱动框架展开的具体特征',
        'total_features': len(unique_features),
        'categories': len(categories),
        'templates': total_templates,
        'features': unique_features
    }

    os.makedirs('outputs/feature_design', exist_ok=True)
    output_path = 'outputs/feature_design/feature_design_doc.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"  💾 保存到: {output_path} ({len(unique_features)} 个特征)")

    # 打印统计
    from collections import Counter
    type_dist = Counter(f.get('data_source', 'unknown') for f in unique_features)
    print(f"\n  数据源分布:")
    for source, count in sorted(type_dist.items(), key=lambda x: -x[1]):
        print(f"    - {source}: {count}个")

    return True


def _build_expand_prompt(categories: list, total_templates: int, fdc_names: set) -> str:
    """构建模板展开Prompt"""

    # 格式化模板信息
    cats_text = ""
    for cat in categories:
        cats_text += f"\n### 类别: {cat['category_name']} ({cat.get('category_name_cn', '')})\n"
        if cat.get('risk_types_covered'):
            cats_text += f"覆盖风险: {', '.join(cat['risk_types_covered'])}\n"
        for t in cat['templates']:
            cats_text += f"\n**模板: {t['template_name']}**\n"
            cats_text += f"业务含义: {t.get('business_meaning', '')[:200]}\n"
            cats_text += f"风险解读: {t.get('risk_interpretation', '')[:200]}\n"
            params = t.get('parameter_space', {})
            if params:
                cats_text += f"参数空间: {json.dumps(params, ensure_ascii=False)}\n"
            formula = t.get('formula_template', '') or t.get('formula', '')
            if formula:
                cats_text += f"公式模板: {formula}\n"

    fdc_examples = list(fdc_names)[:20] if fdc_names else []

    prompt = f"""# 任务：展开特征模板为具体特征列表

## 背景
三阶段风险驱动框架生成了 {len(categories)} 个特征类别、{total_templates} 个特征模板。
现在需要将这些模板展开为具体的、可计算的特征。

## 模板信息
{cats_text}

## 展开规则

### 1. 特征命名规范
- 命名格式: `{{type}}_{{data_source}}_{{description}}_{{time_window}}`
- type: count, ratio, avg, max, min, flag, cross
- data_source: applist, fdc, base

### 2. 数据源映射
- **applist** 字段: appName, packageX, inTime(安装时间戳ms), upTime(更新时间戳ms), appType
- **FDC** 字段: history_inquiry.statistic.3_hari/7_hari/30_hari, pinjaman[].tgl_penyaluran_dana/nilai_pendanaan/sisa_pinjaman_berjalan/dpd_max/dpd_terakhir/status_pinjaman, platform_aktif.jumlahPlatformAktif
- **base** 字段: birthday, salary, job, workYears, marita, children

### 3. 每个特征必须包含
- feature_name: 英文，唯一
- feature_type: count/ratio/avg/max/min/flag/cross
- data_source: applist/fdc/base
- business_explanation_cn: 中文业务解释
- design_reason: 设计理由
- calculation_logic: 具体的Python计算逻辑
- expected_risk_correlation: positive/negative

### 4. 关键约束
- 不要使用 gender 字段（准确率低）
- 每个模板展开3-6个具体特征（不同参数组合）
- 特征数量：总体控制在 50-80 个
- 不要与已有FDC特征重复（FDC特征示例: {json.dumps(fdc_examples, ensure_ascii=False)}）
- FULL format required (anti-time-travel base)

## 输出格式
```json
{{"features": [
  {{
    "feature_name": "count_applist_loanapp_30d",
    "feature_type": "count",
    "data_source": "applist",
    "business_explanation_cn": "近30天安装的贷款类应用数量",
    "design_reason": "多头借贷客群会集中安装多款信贷APP",
    "calculation_logic": "过滤appList中inTime在最近30天的应用，统计category为cash_loan/fintech_lending的应用数",
    "expected_risk_correlation": "positive"
  }}
]}}
```

现在请展开所有模板：
"""
    return prompt


if __name__ == '__main__':
    execute_stepwise_design()
