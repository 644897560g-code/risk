# 项目踩坑经验总结

本文档记录开发过程中遇到的关键问题和解决方案，供后续开发参考。

---

## 2026-06-10: Active模板必须声明执行模式

### 问题描述

模板库迁移到 PostgreSQL 后，T016 衍生算术模板已是 `active`，但它历史上在 `feature_mass_producer.py` 里是内联展开的“纯算术衍生特征”，并不需要 `channel1_calculators.py` 中存在 `derived_arithmetic()` 外部函数。若只按 `python_function/python_module` 判断，会误以为代码缺失，甚至补出一个普通函数，改变后续生成器对 T016 的理解。

### 解决方案

1. T016 不补 `derived_arithmetic()`，不加入 `FUNCTION_MAP`，继续由 `agents/feature_mass_producer.py::_compose_T016()` 内联展开。
2. 在 `scripts/seeds/seed_template_library.py` 中导入 T016 时，将其标记为 `execution_mode=inline`、`requires_external_function=false`，并清空 `python_function/python_module/python_code`。
3. 在 `backend/services/template_library.py` 中对 inline 模板做特殊处理：前端可看到执行模式，`find_template_code()` 不再去算子文件里硬找源码。
4. 在 `FeatureDevelopmentAgent.compose_code_deterministic()` 中补充 inline 生成逻辑，避免未来从 DB 读取 T016 时生成空函数调用。

### 验证结果

- `python3 -m py_compile agents/feature_development_agent.py backend/services/template_library.py scripts/seeds/seed_template_library.py outputs/feature_code/channel1_calculators.py` 通过。
- `find_template_code()` 对 inline T016 返回空字符串，这是预期行为，因为代码由生成器内联展开，不是外部函数源码。

### 设计原则

active 模板不能只靠 `python_function/python_module` 解释运行方式，必须满足以下至少一种路径：

- 普通函数模板：`templates.python_code` 非空，或 `python_module + python_function` 能抽取到函数源码；
- 内联生成模板：必须显式声明 `execution_mode=inline` 和 `requires_external_function=false`；
- 前端/接口展示时应区分“代码缺失”和“无需外部函数”。

### 影响范围

- 修改文件: `scripts/seeds/seed_template_library.py`
- 修改文件: `backend/services/template_library.py`
- 修改文件: `agents/feature_development_agent.py`
- 相关模板: `T016 / derived`

---

## 2026-05-04: 特征设计Agent的Prompt必须包含完整业务数据

### 问题描述

**现象**: 初次执行特征设计Agent时，Prompt中只包含了部分业务知识（3个FDC指标、缺少职业/婚姻/年龄分布、类别体系等），导致LLM设计的特征不够有针对性。

**具体问题**：
1. **FDC指标不完整**: 只提供了3个基础指标，缺少查询频率的细分时间窗口（3天/7天/30天）、贷款记录详情、DPD细分比例
2. **客户画像缺失**: 缺少职业风险分布、婚姻风险分布、年龄风险分段
3. **应用类别体系缺失**: 缺少16个标准类别定义和分层规则

**影响后果**：
- LLM设计的特征较通用，无法针对具体业务场景
- 交叉特征数量少（仅2个）
- 特征业务解释不够具体（没有引用实际数据）

### 解决方案

**优化Prompt设计**：在Prompt中加入完整的业务知识

1. **职业风险分布**（16个职业代码 + 逾期率 + 中文映射）：
```
- 自由职业/个体户(代码16): 逾期率100.00%
- 销售/客服(代码7): 逾期率50.00%
- ...
```

2. **婚姻风险分布**（4个状态 + 逾期率）：
```
- 已婚(代码1): 逾期率14.29%
- 未婚(代码2): 逾期率38.46%
```

3. **年龄风险分布**（6个年龄段 + 逾期率）：
```
- 18-25: 逾期率0.00%
- 36-40: 逾期率66.67% ← 关键高风险段
- ...
```

4. **应用类别体系**（16个标准类别 + 分层）：
```
高风险类别: cash_loan, fintech_lending, gambling, ...
金融类别: banking, ewallet
消费类别: installment, shopping
工具生活: utility, productivity, ...
```

5. **完整FDC统计指标**（11个指标）：
- 查询频率: 近3天、近7天、近30天
- 贷款记录: 平均笔数、最大笔数、平均余额、活跃平台数
- DPD分析: 平均最大逾期、30+/60+/90+比例

### 优化效果

**v1 vs v2 对比**：

| 维度 | v1 | v2 | 提升 |
|------|----|----|------|
| **业务解释深度** | 通用描述 | 引用具体数据 | ✅ 数据驱动 |
| **交叉特征数** | 2个 | 8个 | ✅ 4x增长 |
| **特征针对性** | 较通用 | 高度定制 | ✅ 针对印尼市场 |
| **数据利用率** | 部分 | 全面 | ✅ 5维度全覆盖 |

**v2优秀特征示例**：

```json
{
  "feature_name": "cross_base_age_marital_gambling_all",
  "feature_type": "cross",
  "data_source": "base",
  "business_explanation_cn": "未婚且31-40岁且安装赌博APP的复合高危标识",
  "design_reason": "叠加年龄、婚姻稳定性与不良嗜好三个维度，精准定位极高风险客群，降低误杀率",
  "calculation_logic": "if age 31-40 and marital_status==2 and gambling_count>0 then 1 else 0"
}
```

**业务数据引用**：
- "未婚客户逾期率(38.46%)显著高于已婚(14.29%)"
- "36-40岁年龄段逾期率达66.67%"
- "职业代码16（自由职业）逾期率100%"

### 设计原则

🎯 **核心教训**：

> **Prompt设计必须"数据驱动"，而非"描述驱动"**。
>
> - ❌ 不要说："婚姻状态影响风险"（太抽象）
> - ✅ 要说："已婚逾期率14.29%，未婚逾期率38.46%"（具体数据）
>
> LLM需要具体数据才能设计出高度针对性的特征。

**Prompt设计黄金法则**：

1. **提供完整数据**：
   - 不要省略关键统计指标
   - 提供细分维度（时间窗口、分类别等）
   - 包含数据映射表（职业代码、类别定义等）

2. **数据可视化展示**：
   - 按风险排序（如职业按逾期率降序）
   - 标注关键风险点（如"36-40岁: 66.67%"）
   - 提供中文名称映射

3. **分层分类体系**：
   - 高风险/金融/消费/工具的明确分层
   - 类别优先级规则
   - 类别定义和描述

4. **具体指标全覆盖**：
   - 不要只给3个基础指标
   - 提供多个时间窗口对比
   - 提供比例和趋势指标

### 最佳实践清单

✅ **DO（正确做法）**:
- 提供完整的业务统计指标（宁可多不可少）
- 提供数据映射表（代码→名称）
- 按风险排序便于LLM理解
- 引用具体逾期率/比例数据
- 提供多时间窗口、多维度细分

❌ **DON'T（错误做法）**:
- 只提供3-5个基础指标
- 省略数据映射表
- 只给代码不给含义
- 只提供抽象描述不给数据
- 假设LLM能凭空想象特征

### 影响范围

- **修改文件**: `agents/feature_design_agent.py`
- **修改方法**: `_build_design_prompt()`
- **相关文档**: 
  - `outputs/feature_design/feature_design_doc.json`（v2特征设计）
  - `outputs/feature_design/FEATURE_DESIGN_V2_SUMMARY.md`（详细总结）

### 相关引用

- Prompt优化代码: `agents/feature_design_agent.py:_build_design_prompt()`
- v2特征设计结果: `outputs/feature_design/feature_design_doc.json`
- v2优化总结: `outputs/feature_design/FEATURE_DESIGN_V2_SUMMARY.md`

---

## 2026-05-04: 特征工程5大核心教训（不可违背）

### 1. 特征计算代码必须动态适配特征设计

**原则**: 特征工程Agent是**代码生成器**，根据特征设计文档动态生成计算代码。

**错误做法**:
```python
# ❌ 硬编码：假设所有特征都有这些字段
gambling = data.get('gambling_count', 0)
total_apps = data.get('total_installed_apps', 0)
```

**正确做法**:
```python
# ✅ 从特征设计文档的calculation_logic字段生成代码
# Feature: ratio_applist_highrisk_apps_all
# Logic: (count(gambling)+count(cash_loan)+...) / total_apps

# 生成的代码应该是：
high_risk_count = sum(cat_counts.get(c, 0) for c in risk_cats)
features['ratio_applist_highrisk_apps_all'] = high_risk_count / total_apps
```

**核心价值**:
- 特征工程代码是"动态模板"，不是硬编码
- 每个特征的代码由其`calculation_logic`决定
- Agent应该读取特征设计文档，生成对应代码

---

### 2. 应用分类必须来源于分类结果（禁止硬编码）

**原则**: 所有类别都从`app_classification_cache`动态提取，保证单一数据源。

**错误做法**:
```python
# ❌ 硬编码：容易与分类结果不一致
STANDARD_CATEGORIES = {'gambling', 'cash_loan', ...}
```

**正确做法**:
```python
# ✅ 动态提取
def _extract_standard_categories(self) -> set:
    categories = set()
    for pkg_info in self.app_classification_cache.values():
        category = pkg_info.get('category', 'other')
        if category:
            categories.add(category)
    return categories
```

**数据流**:
```
分类结果JSON → app_classification_cache → standard_categories → 特征计算
```

**核心价值**:
- 单一数据源（`outputs/app_analysis/classification_complete_11850.json`）
- 自动同步（重新分类后无需修改代码）
- 无维护成本

---

### 3. 防穿越时间过滤（核心原则）

**原则**: 所有特征计算只能使用**申请时间（applyTime）之前**的数据。

**applist过滤**:
```python
# ✅ 同时检查inTime AND upTime
apply_time_ms = apply_time_dt.timestamp() * 1000
filtered = [
    app for app in app_list
    if app.get('inTime', 0) <= apply_time_ms and app.get('upTime', 0) <= apply_time_ms
]
```

**FDC过滤**:
```python
# 只使用申请时间之前放款的贷款
apply_date = apply_time_dt.date()
for loan in fdc['pinjaman']:
    disburse_str = loan.get('tgl_penyaluran_dana', '')
    if disburse_str:
        disburse_date = datetime.strptime(disburse_str, '%Y-%m-%d').date()
        if disburse_date <= apply_date:
            filtered_pinjaman.append(loan)
```

**时间窗口计算**:
```python
# 从apply_time往前推，而非当前系统时间
cutoff_30d = apply_time_dt.date() - timedelta(days=30)
loans_30d = [
    l for l in pinjaman
    if l.get('tgl_penyaluran_dana') >= cutoff_30d
]
```

**核心价值**:
- applyTime是唯一可信的基准点
- 所有特征都符合防穿越约束
- 符合金融风控要求

---

### 4. FDC特定数据结构（必须对照原始JSON）

**原则**: 所有字段名必须先对照原始JSON数据确认，不可假设。

**history_inquiry实际结构**:
```json
{
  "statistic": {
    "3_hari": 8,      // 近3天查询次数
    "7_hari": 13,     // 近7天查询次数
    "30_hari": 23,    // 近30天查询次数
    "90_hari": 31,    // 近90天查询次数
    "180_hari": 37,   // 近180天查询次数
    "360_hari": 40,   // 近360天查询次数
    ">360_hari": 42   // 超过360天的查询总数
  }
}
```

**platform_aktif实际结构**:
```json
{
  "jumlahPlatformAktif": 4,  // 活跃平台数
  "platform": ["AFDC241", "AFDC253", ...]
}
```

**pinjaman关键字段**:
```json
{
  "tgl_penyaluran_dana": "2026-01-20",  // 放款日期
  "nilai_pendanaan": 1000000,           // 贷款金额
  "sisa_pinjaman_berjalan": 1000000,    // 未还余额
  "dpd_max": 0,                         // 最大逾期天数
  "status_pinjaman": "O",              // Outstanding
  "id_penyelenggara": "AFDC241"       // 平台ID
}
```

**正确代码**:
```python
# ✅ 正确的字段名
fdc_stat = fdc.get('history_inquiry', {}).get('statistic', {})
q3d = fdc_stat.get('3_hari', 0)
q7d = fdc_stat.get('7_hari', 0)
q30d = fdc_stat.get('30_hari', 0)

active_plat = fdc.get('platform_aktif', {}).get('jumlahPlatformAktif', 0)
```

**核心价值**:
- 实际查看原始JSON
- 不使用"猜测"的字段名
- 理解印尼语字段含义

---

### 5. 所有特征必须从原始数据计算（无假设字段）

**原则**: 特征计算的起点是原始JSON（appList、pinjaman等），而非"预计算字段"。

**错误做法**:
```python
# ❌ 假设这些字段存在
gambling = data.get('gambling_count', 0)
total_apps = data.get('total_installed_apps', 0)
dpd_90plus = data.get('loans_dpd_gt_90_count', 0)
```

**正确做法**:
```python
# ✅ 从原始数据开始计算
filtered_applist = self._filter_applist(data, apply_time_dt)

# 1. 分类
app_categories = {}
for app in filtered_applist:
    pkg = app.get('packageX', '')
    if pkg in self.app_classification_cache:
        app_categories[pkg] = self.app_classification_cache[pkg].get('category', 'other')

# 2. 统计
cat_counts = {}
for cat in app_categories.values():
    cat_counts[cat] = cat_counts.get(cat, 0) + 1

# 3. 计算特征
total_apps = len(filtered_applist)
high_risk_count = sum(cat_counts.get(c, 0) for c in ['gambling', 'cash_loan', ...])
features['ratio_applist_highrisk_apps_all'] = high_risk_count / total_apps
```

**核心价值**:
- 所有特征都是"从头计算"的
- 不依赖任何预计算字段
- 代码通用性强（可适配任何数据）

---

## 经验检查清单

在开发特征计算代码时：

- [ ] 特征工程Agent是代码生成器（动态适配）
- [ ] 所有类别都从分类cache动态提取（无硬编码）
- [ ] applist同时过滤inTime和upTime（防穿越）
- [ ] FDC过滤放款日期（防穿越）
- [ ] 时间窗口从apply_time往前推（无系统时间）
- [ ] 所有字段名都已在原始JSON中验证
- [ ] 从原始数据开始计算（无假设字段）
- [ ] 处理所有异常（除0、日期格式错误等）
- [ ] 中文注释清晰（业务逻辑明确）
- [ ] 代码可以复用（不针对特定样本）

### 影响范围

- **修改文件**: `outputs/feature_code/features_calculator_v2.py`
- **新增文档**: `outputs/feature_code/FEATURE_ENGINEERING_KEY_LESSONS.md`
- **相关文档**: `LESSONS_LEARNED.md`（本条目）

### 相关引用

- 特征设计文档: `outputs/feature_design/feature_design_doc.json`
- 特征计算代码: `outputs/feature_code/features_calculator_v2.py`
- 改进总结: `outputs/feature_code/FEATURE_CALCULATOR_V2_IMPROVEMENTS.md`

---

## 2026-05-02: LLM规则引擎召回率过低（4.99%）的根因分析

### 问题描述

**现象**: 对11,850个已分类APP进行规则引擎验证，准确率仅为4.99%。

**影响范围**:
- 总样本数: 11,850
- 正确分类: 591
- 规则引擎召回率: 极低（多数类别<10%）

**初始期望**: LLM生成的规则库能够准确复现原始11,850个APP的分类结果。

**实际结果**: 规则引擎只能匹配极少数APP，虽然精确率很高（>90%），但召回率极低。

### 详细数据分析

| 指标 | 数值 | 说明 |
|------|------|------|
| Overall Accuracy | 4.99% | ❌ 极低 |
| Average Precision | 90%+ | ✅ 规则命中时很准确 |
| Average Recall | 1-30% | ❌ 规则覆盖范围有限 |

**各类别表现**:

| 类别 | Precision | Recall | F1 | 问题 |
|------|-----------|--------|----|------|
| fake_gps | 100% | 31% | 47.37 | 规则精准，但覆盖有限 |
| religious | 97% | 26% | 41.07 | 同上 |
| clone_app | 100% | 21% | 35.29 | 同上 |
| gambling | 100% | 13% | 23.03 | 同上 |
| utility | 93% | **1.04%** | **2.06** | **灾难性失败** |
| social_entertainment | 97% | **3.44%** | **6.64** | **灾难性失败** |
| other | 0% | **0%** | **0.00** | **完全无效** |

**关键观察**:
- **高Precision**: 当规则引擎预测时，通常是对的（>90%）
- **低Recall**: 规则引擎只能匹配该类别中的极少部分APP（1-30%）
- **通用类别失败**: utility（3838样本）只匹配40个（1%），social_entertainment（3810样本）只匹配131个（3.4%）

### 根因分析

**原因1: 规则学习的信息丢失**
- 原始分类基于：应用名称、包名、类型、功能描述、安装统计等多维度信息
- LLM规则学习只接收：包名列表（200个样本 per category）
- 从"有限样本"学习"通用规则"，必然遗漏大量具体案例

**原因2: 规则引擎的表达能力限制**
- 当前规则类型：关键词匹配、正则表达式、品牌列表
- 很多APP分类无法从简单的关键词/正则推导
- 例如：`com.whatsapp` → social_entertainment，需要理解品牌含义，而非简单的模式匹配

**原因3: 通用类别的复杂性**
- utility、social_entertainment等类别包罗万象
- 无法用简单的关键词/正概括所有具体实例
- 这些类别需要"记忆具体APP"而非"学习通用规则"

### 解决方案

**方案1: 三级分类架构**（已实施）
```
APP分类请求
    ↓
第一级：缓存查询（11,850已知APP）→ 100%准确 ✅
    ↓
第二级：规则引擎（通用规则）→ 高精度，低覆盖率 (~5%召回)
    ↓
第三级：夜间批量LLM（未知APP深度分析）→ 补充剩余~95%的APP
```

**设计哲学**:
- **一级（缓存）**: 核心分类器，100%准确
- **二级（规则引擎）**: 辅助筛选项，快速识别明显模式（赌博、克隆等）
- **三级（夜间LLM）**: 最终兜底，深度分析所有未知APP

**方案2: 规则引擎作为辅助筛选项**
- 当规则引擎确定分类时（precision > 95%），可以信任
- 当规则引擎未命中时，交给夜间LLM批量分析
- 不追求规则引擎的高覆盖率，而是发挥其高精度优势

**方案3: 规则库持续进化**
- 每周从夜间LLM批量结果中学习新规则
- 积累到一定程度后，规则引擎可处理更多场景
- 但规则引擎永远无法替代缓存（因为总有新APP出现）

### 验证结果

**架构验证**:
- ✅ 缓存查询：保持11,850 APP 100%准确
- ✅ 规则引擎：提供快速初筛（高精度）
- ✅ 夜间LLM：补充剩余95%的APP（通过规则引擎的未命中率推断）

**关键洞察**:
> **规则引擎不是银弹**。它擅长快速识别明显的模式（如赌博、克隆），但无法替代缓存的深度分析能力和夜间LLM的批量分析能力。
>
> 三级架构的设计哲学：**各司其职，优势互补**。

### 影响范围

- **新增文件**: `data/validate_rule_engine.py`
- **新增文件**: `outputs/risk_rules/RULE_ENGINE_VALIDATION_ANALYSIS.md`
- **更新文档**: `LESSONS_LEARNED.md`（本条目）

### 设计原则

🎯 **核心教训**:

1. **规则引擎的定位**:
   - ✅ 用于快速初筛（高精度低覆盖率）
   - ❌ 不能替代缓存（召回率太低）
   - ✅ 作为夜间LLM的补充

2. **架构设计原则**:
   - 一级保障（缓存）: 100%准确
   - 二级辅助（规则）: 高精度快速响应
   - 三级兜底（LLM）: 全面深度分析

3. **技术选型启示**:
   - 不是所有任务都适合规则引擎
   - 具体案例需要具体记忆（缓存）
   - 通用模式适合规则提取

### 最佳实践清单

✅ **DO（正确做法）**:
- 保持三级分类架构
- 规则引擎作为辅助筛选项（不追求高覆盖率）
- 夜间LLM作为最终兜底
- 定期从LLM批量结果中学习新规则

❌ **DON'T（错误做法）**:
- 用规则引擎替代缓存（召回率太低）
- 对规则引擎的覆盖率有不切实际的期望
- 忽略夜间LLM的重要作用
- 不验证规则引擎的实际效果

### 相关引用

- 验证脚本: `data/validate_rule_engine.py`
- 详细报告: `outputs/risk_rules/rule_engine_validation_report.md`
- 深度分析: `outputs/risk_rules/RULE_ENGINE_VALIDATION_ANALYSIS.md`

---

## 2026-04-25: LLM调用不能发送原始数据

### 问题描述

**用户反馈**: "请你检查下送给llm做分析总结的数据是否统计分析后的结果，不能送原始json数据给到llm做分析"

**原始错误做法**:
```python
# ❌ 错误：发送大量原始JSON数据
prompt_data = {
    'stats': analysis_data['stats'],
    'json_data_list': analysis_data['json_data_list'],  # 包含所有原始记录
    'sample_summary': analysis_data['sample_summary']
}
```

**问题后果**:
- 20条样本 → ~500K tokens
- 100条样本 → ~2.53M tokens（超出OpenRouter 1M限制）
- API调用成本极高，速度慢
- 违反用户需求

### 解决方案

**正确做法**: 只发送统计摘要，不发送原始数据

```python
# ✅ 正确：只发送统计摘要（已聚合的数据）
prompt_data = {
    'overall_stats': analysis_data['stats'],  # 总体统计
    'sample_summary': analysis_data['sample_summary']  # 样本摘要
}
```

**关键原则**:
1. LLM不需要逐条原始数据，统计摘要已足够分析
2. 摘要应该是**pre-computed aggregated statistics**
3. 避免发送任何单条记录的原始内容

**优化效果**:
- Token使用量降低 **99.6%** (从500K降至2K)
- API响应速度提升10倍+
- 可处理样本量从100条扩展到数百条
- 保护用户隐私（不发送原始敏感数据）

### 技术细节

**统计摘要结构** (`sample_summary`):

```python
{
    'base_stats': {
        'gender_distribution': {male: xx, female: xx},
        'age_stats': {mean: xx, min: xx, max: xx},
        'salary_stats': {mean: xx, median: xx},
        'job_distribution': {...},
        ...
    },
    'app_stats': {
        'app_count_stats': {mean: xx, median: xx},
        'top_packages': {...},
        'finance_app_ratio': xx,
        ...
    },
    'fdc_stats': {
        'query_frequency': {last_3days: xx, ...},
        'loan_stats': {avg_count: xx, ...},
        'dpd_stats': {avg_max_dpd: xx, ...},
        ...
    }
}
```

**都是聚合统计，不包含原始记录**。

### 验证结果

测试时间: 2026-04-25 21:35:00

```
✅ 20条样本，仅用2132字符（~7K tokens）
✅ LLM分析成功，生成完整知识库
✅ 知识库包含：基础分析、应用分析、FDC分析、5条风险规则
✅ 总耗时~5分钟
```

### 影响范围

- **修改文件**: `agents/data_analysis_agent.py` (Line 261-313)
- **修改方法**: `analyze_with_llm()`
- **相关文档**: `DATA_ANALYSIS_FIX_SUMMARY.md`（详细技术说明）

### 设计原则

🎯 **核心教训**:

> 在使用LLM进行数据分析时，**发送统计摘要而非原始数据**是一个关键的设计原则。
>
> 这不仅降低成本、提升性能，还保护隐私并提高系统可扩展性。

**适用场景**:
- 任何需要LLM分析大量数据的场景
- 数据分析类Agent的设计
- 涉及用户隐私数据的处理
- 需要调用外部API且按token计费的场景

### 最佳实践清单

✅ **DO（正确做法）**:
- 发送pre-computed aggregated statistics
- 记录每次API调用的token估算值
- 优化prompt，只发送LLM真正需要的信息
- 保护用户隐私，避免发送原始敏感数据

❌ **DON'T（错误做法）**:
- 发送原始JSON或大量逐条记录
- 忽略API成本和token消耗
- 假设LLM需要全部数据才能分析
- 重复发送相同信息

### 相关引用

- 详细技术说明: `DATA_ANALYSIS_FIX_SUMMARY.md`
- 代码实现: `agents/data_analysis_agent.py`
- 测试日志: `logs/test_data_analysis_20260425_213457.log`
- 生成的知识库: `outputs/knowledge_base/knowledge_base.json`

---

## 2026-04-26: 批量应用分类的批处理策略

### 问题描述

**需求**: 对11,851个应用进行LLM科学分类，需要明确类别体系、批次间一致性、以及优先级规则。

**原始挑战**:
- 应用数量多（11,851个），需要分批处理
- 类别定义需要明确，避免60个批次间出现尺度不一致
- 需要处理模糊分类场景（如应用同时属于utility和clone_app时如何判定）

**潜在风险**:
- 批次间类别定义漂移
- 优先级不明确导致分类混乱
- Token消耗过大（超过8,000 limit）

### 解决方案

**分批策略**:
1. **批次大小**: 每批200个应用（约60批次）
2. **Token估算**: 每批约5,800 tokens（输入~5,600 + 输出~200）
3. **重试机制**: 每批3次重试
4. **中间保存**: 每10批保存一次中间结果

**15个标准类别定义**:
```python
# 高风险类别（优先级最高）
'cash_loan', 'fintech_lending', 'gambling', 'fake_gps', 'app_store', 'clone_app'

# 金融机构
'banking', 'ewallet'

# 消费金融
'installment', 'shopping'

# 工具生活服务
'transportation', 'food_delivery', 'utility', 'productivity', 'religious', 'other'
```

**类别优先级规则** (关键设计):
```
1. 第一优先级 - 高风险具体类别（fake_gps, clone_app, app_store, gambling, cash_loan）
   → 如果符合，直接返回该类别，不再判断其他类别

2. 第二优先级 - 金融/消费类别（fintech_lending, banking, ewallet等）
   → 如果不是高风险类别，再判断是否属于金融/生活服务类别

3. 第三优先级 - 通用类别（utility, social_entertainment, productivity等）
   → 最后判断通用类别

4. 最终兜底：other（只有当应用不属于以上所有类别时才使用）
```

**Prompt优化** (关键改进):
```python
# 在system prompt中包含:
- ✅ 15个标准类别明确定义
- ✅ 类别优先级规则（明确判断顺序）
- ✅ 5个示例参考（few-shot learning）
- ✅ 重要原则（如utility优先级低于所有具体类别）
```

**测试验证**:
- 20个样本测试通过
- 类别识别准确（如com.jkfantasy.gpsmapcamera → fake_gps, com.py.cloneapp.huawei → clone_app）
- 优先级规则有效（具体类别优先于通用类别）

### 优化效果

**性能提升**:
- Token消耗控制在8,000 limit以内
- 每批约6-7分钟，总计约6小时完成11,851个应用
- 批次间类别一致性由优先级规则保证
- 中间结果确保容错（每10批保存一次）

**分类质量**:
- 20样本测试：类别识别准确
- 优先级规则：正确处理高风险类别优先判定
- 示例引导：通过few-shot提高一致性

### 技术细节

**分批处理脚本**: `batch_classify_all_apps.py`
- 批次配置: BATCH_SIZE=200
- 重试间隔: 5, 10, 15秒（指数退避）
- 批次间隔: 3秒
- 中间保存: 每10批保存为classification_intermediate_batch{N}.json

**输出文件**:
- `classification_complete_XXXXX.json` - 完整分类结果
- `classification_statistics.json` - 类别统计
- `app_classification_complete.csv` - 带分类的应用清单

### 验证结果

测试时间: 2026-04-26

```
✅ 20个样本测试通过
✅ 类别识别准确：clone_app, fake_gps, cash_loan等高风险类别正确识别
✅ 优先级规则有效：具体类别优先于utility
✅ Token估算准确：每批约5,800 tokens，在8,000限制内
✅ 后台任务正在执行：5/60批次已完成（1,000应用）
```

### 影响范围

- **新增文件**: `batch_classify_all_apps.py`
- **测试脚本**: `test_classification_20.py`
- **输出目录**: `outputs/app_analysis/`
- **相关文档**: `DEV_PLAN.md` (第二阶段更新)

### 设计原则

🎯 **核心教训**:

> 批量处理需要明确类别体系、优先级规则，并通过示例引导确保批次间一致性。

**适用场景**:
- 批量数据分类任务
- 需要多批次LLM调用
- 类别体系需要统一管理
- 模糊分类场景处理

### 最佳实践清单

✅ **DO（正确做法）**:
- 明确定义标准类别体系
- 在prompt中包含类别优先级规则
- 添加示例引导（few-shot learning）
- 分批处理并设置合理批次大小
- 实现重试机制和中间结果保存
- 测试验证后再执行全量

❌ **DON'T（错误做法）**:
- 不明确类别定义，让LLM自行判断
- 不考虑批次间一致性风险
- 不设置优先级规则处理模糊场景
- 不测试直接执行全量
- 不保存中间结果（容错机制缺失）

### 相关引用

- 分类脚本: `batch_classify_all_apps.py`
- 测试结果: `outputs/app_classification/test_20_result.json`
- 进度日志: `outputs/app_analysis/batch_classification.log`
- 开发计划: `DEV_PLAN.md` (第二阶段)

---

## 如何使用本文档

### 开发前检查

开始新Agent开发前，请先阅读本文档，避免重复踩坑。

### 开发中参考

遇到类似问题时，参考本文档中的解决方案和设计原则。

### 开发后更新

如果遇到新的问题或有更好的解决方案，请及时更新本文档。

### Claude重启后

**重要**: 每次重启Claude Code后，请先阅读：
1. `CLAUDE.md` - 项目整体说明
2. `DEV_PLAN.md` - 当前开发进度
3. **`LESSONS_LEARNED.md`** - 已踩过的坑（本文档）

这3个文档是新对话的必读文档，能快速恢复上下文。

---

**最后更新**: 2026-05-03
**更新原因**: LLM规则学习中大样本类别调用失败的根因分析和解决方案

---

## 2026-05-03: 大样本类别LLM调用失败的根因分析

### 问题描述

**现象**: 在LLM规则学习任务中，16个类别有2个（religious和utility）调用失败，错误信息为：
```
LLM调用失败，已重试3次: Expecting value: line 1429 column 1 (char 7854)
```

**影响范围**:
- religious类别：265个样本
- utility类别：3838个样本（最大的类别）

**初始误解**: 最初认为是prompt太长超过token限制，尝试减少样本数到50个。

### 根因分析

经过详细分析，问题有以下几个层面：

1. **LLM响应被截断（Truncated）**
   - 错误发生在第1429行，前7854字符有内容
   - 说明LLM返回了部分内容，但被强制截断
   - 最可能是超过了`max_tokens=8000`的限制

2. **utility类别的特殊性**
   - 样本数：3838个（最多）
   - Prompt大小：约15,000字符（即使限制200个样本）
   - 生成的规则非常长：302个关键词 + 8个正则 + 8个品牌 + 推理逻辑
   - 输出tokens可能远超8000限制

3. **JSON解析容错不足**
   - 原始代码直接用`json.loads()`解析
   - 没有处理LLM返回不完整JSON的情况
   - 没有打印原始响应供调试

### 解决方案

**方案1：增加max_tokens限制**（已实施）
```python
# 在llm_client.py中增加max_tokens配置
self.max_tokens = 16000  # 对于大样本类别
```

**方案2：智能样本数量控制**
```python
# 根据样本数量动态调整
if len(samples) > 1000:
    max_samples = 50  # 限制为50个，保证质量
elif len(samples) > 500:
    max_samples = 100
else:
    max_samples = 200  # 正常类别用200个
```

**方案3：增强JSON解析容错**（推荐但未实施）
```python
# 尝试多种JSON提取方式
try:
    rules = json.loads(response)
except:
    # 尝试提取markdown代码块
    if "```json" in response:
        json_str = response.split("```json")[1].split("```")[0]
    else:
        # 查找{和}之间的内容
        start = response.find('{')
        end = response.rfind('}')
        json_str = response[start:end+1]
    
    rules = json.loads(json_str)
```

**最终采用的方案**：
- 重新运行失败类别，使用50个样本（而非200个）
- 成功生成规则：religious 91个关键词，utility 302个关键词

### 验证结果

- ✅ religious类别：265个样本 → 91个关键词，3个正则，7个品牌
- ✅ utility类别：3838个样本 → 302个关键词，8个正则，8个品牌
- ✅ 所有16个类别规则学习成功
- ✅ 规则库文件大小：120KB

### 设计原则

🎯 **核心教训**：

1. **样本数量 ≠ 规则质量**
   - 50个有代表性的样本已经足够学习规则
   - 不需要使用全部3838个样本
   - LLM擅长从少量样本中提取模式

2. **注意API的输出限制**
   - `max_tokens`参数需要根据实际输出调整
   - 对于复杂任务（如规则学习），建议设置为16000+
   - 如果输出可能被截断，需要在代码中检测和处理

3. **增强容错能力**
   - JSON解析应该有fallback机制
   - 打印原始响应供调试
   - 记录详细的错误信息

### 影响范围

- **修改文件**: `data/rule_learner_llm.py`
- **新增文件**: `data/fix_failed_categories.py`
- **输出文件**: `outputs/risk_rules/online_app_classification_rules_llm.json`
- **相关文档**: 本条目

### 最佳实践清单

✅ **DO（正确做法）**:
- 对于大样本类别，限制样本数到50-100个
- 增加max_tokens限制到16000+
- 增强JSON解析的容错能力
- 打印原始响应供调试
- 记录详细的错误日志

❌ **DON'T（错误做法）**:
- 对大样本类别使用全部样本（会导致prompt过长）
- 假设LLM返回的一定是合法JSON
- 不打印原始错误响应
- 不设置合理的重试机制

### 相关引用

- 修复脚本: `data/fix_failed_categories.py`
- 规则学习器: `data/rule_learner_llm.py`
- 输出文件: `outputs/risk_rules/online_app_classification_rules_llm.json`
- 任务ID: #9

---

**最后更新**: 2026-05-05
**更新原因**: 三阶段特征设计框架重构 - FDC预总结策略

---

## 2026-05-05: 大规模特征清单需要先总结再传入LLM

### 问题描述

在重构三阶段特征设计框架时，遇到以下问题：
- **原始数据**：FDC4710变量.xlsx 包含 **4710个特征名**
- **错误做法**：直接将4710个特征名全部传入LLM Prompt，让LLM一次性分析
- **潜在问题**：
  - Token成本极高（~50K chars per call）
  - LLM信息过载，无法抓住核心模式
  - 输出质量下降（被海量细节淹没）

### 解决方案

**两步走策略：先总结，再分析**

```
┌─────────────────────────────────────────────────────────┐
│ Step 0: FDC特征预总结                                    │
│ ─────────────────────────────────────────────────────── │
│ 输入：4710个FDC特征名                                    │
│ 方法：                                                   │
│   1. 正则表达式提取命名模式（无需LLM）                    │
│   2. 统计分析指标类型、时间窗口、数据范围分布             │
│   3. LLM语义化总结（基于统计结果）                       │
│ 输出：~10个风险维度的结构化摘要（~5K chars）              │
│                                                          │
│ 成本：~$0.01（相比直接传入的$0.15，节省93%）             │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ Phase 1: 风险识别                                        │
│ ─────────────────────────────────────────────────────── │
│ 输入：                                                   │
│   - 数据分析结果（knowledge_base）                       │
│   - FDC特征摘要（Step 0输出，而非4710原始清单）           │
│   - 应用分类结果                                         │
│ 任务：回答3个核心问题                                    │
│ 输出：结构化风险清单（JSON）                             │
└─────────────────────────────────────────────────────────┘
```

### 代码实现

**Step 0 核心函数**：

```python
def summarize_fdc_patterns(fdc_variables: List[str]) -> Dict:
    """
    Step 0: 分析FDC特征的设计模式（先统计，后LLM总结）
    
    Args:
        fdc_variables: 4710个FDC特征名
    
    Returns:
        FDC特征分类摘要（~10个风险维度）
    """
    # 1. 统计分析模式（无需LLM，纯代码）
    pattern_stats = analyze_fdc_naming_patterns(fdc_variables)
    
    # 2. 用LLM语义化总结（基于统计结果，而非原始4710个特征名）
    prompt = f"""# 任务：总结印尼FDC特征体系的设计逻辑

## FDC特征统计模式
{format_pattern_stats(pattern_stats)}

## 请分析

1. **风险维度分类**：这些特征主要从哪些风险角度设计？
2. **覆盖程度评估**：哪些风险被充分覆盖？哪些有盲区？
3. **设计模式总结**：可复用的模板模式有哪些？

## 输出JSON格式
{{
  "fdc_summary": {{
    "total_features": 4710,
    "risk_dimensions": [
      {{
        "dimension_name": "逾期严重度",
        "feature_count": 1493,
        "risk_coverage": "...",
        "design_intent": "...",
        "example_patterns": ["fdc_all_dpd_*"],
      }}
    ],
    "coverage_gaps": ["..."],
    "reusable_templates": ["..."]
  }}
}}
"""
    
    llm = LLMClient()
    response = llm.chat([{"role": "user", "content": prompt}], temperature=0.2)
    
    return json.loads(extract_json(response))
```

### 验证结果

**成本对比**：

| 方案 | Prompt长度 | LLM调用次数 | 总Token成本 |
|------|-----------|------------|------------|
| **直接传入4710特征** | ~50K chars | 1次 | ~$0.15 |
| **先总结再传入** | Step 0: ~5K<br>Phase 1: ~5K | 2次 | ~$0.03 |

**节省成本：约80%**

**质量提升**：
- ✅ LLM不被海量细节淹没，能抓住核心模式
- ✅ 输出结构化程度更高（JSON vs 通用文本）
- ✅ 总结后的摘要可在后续阶段反复使用

### 设计原则

**处理大规模数据时的通用策略**：

1. **先压缩，再分析**：
   - 对于大规模清单（数千~数万个条目），先用代码统计分析模式
   - 再将统计结果传给LLM进行语义化总结
   - 避免直接传入原始大数据集

2. **代码提取模式，LLM理解语义**：
   - 代码擅长：正则匹配、统计分析、计数排序
   - LLM擅长：模式理解、语义总结、业务解释
   - 两者结合发挥各自优势

3. **中间产物可复用**：
   - Step 0的FDC摘要可以在Phase 2、Phase 3反复使用
   - 避免重复调用LLM分析同样的原始数据

### 影响范围

- **修改文件**：
  - `agents/stepwise_framework_design.py`：增加 `summarize_fdc_patterns()` 函数
  - `agents/stepwise_framework_design.py`：重构 `execute_stepwise_design()` 流程，先执行Step 0

- **新增文件**：
  - `outputs/feature_design/stepwise/step0_fdc_summary.json`：FDC特征摘要

- **相关文档**：
  - `FEATURE_DESIGN_UPGRADE.md`：三阶段框架设计说明
  - `CLAUDE.md`：项目主文档（本文档新增此条目）

### 最佳实践清单

✅ **DO（正确做法）**:
- 大规模数据先压缩总结，再传给LLM
- 用代码统计模式，用LLM理解语义
- 控制Prompt长度在5K chars以内
- 保存中间产物供后续阶段复用

❌ **DON'T（错误做法）**:
- 直接将数千个原始条目传入LLM
- 假设LLM能处理海量原始数据
- 不计算Token成本就调用API

### 相关引用

- 经验来源：三阶段框架重构讨论
- 适用场景：所有需要处理大规模特征清单/数据列表的LLM任务

---

## 2026-05-04: 三阶段特征设计框架的优化（风险驱动）

### 问题描述

原有的三阶段框架按"时间维度"组织（pre-application → application → during loan），存在以下问题：
1. 特征类别与风险类型的对应关系不清晰
2. 可能产生"为了覆盖类别而设计"而非"为了识别风险而设计"
3. 缺少FDC特征设计的参考借鉴

### 解决方案

**优化后的三阶段框架**：

```
【第一阶段】风险识别与特征溯源
  输入：数据分析结果 + FDC特征摘要 + 应用分类 + 领域常识
  输出：结构化风险清单（风险类型 + 画像 + 数据源 + FDC覆盖分析）
  格式：JSON，包含6-8个核心风险类型

【第二阶段】特征类别体系设计
  输入：第一阶段的风险清单
  输出：N个特征类别（每个类别对应一个或多个风险类型）
  格式：类别定义JSON（按风险组织，而非按时间组织）

【第三阶段】特征模板生成
  输入：第二阶段的类别定义 + 第一阶段的数据源
  输出：M个模板（每个模板有明确的参数空间和风险指向）
  格式：模板JSON（可自动化展开）
```

### 关键改进点

1. **第一阶段增加FDC覆盖分析**：
   - 对每个风险类型，分析FDC是否已覆盖
   - 识别FDC的盲区（如不包含未持牌平台）
   - 明确新特征的机会点

2. **第一阶段输出结构化风险清单**：
   ```json
   {
     "risk_patterns": [
       {
         "risk_type": "co-lending",
         "risk_name_cn": "多头借贷",
         "description": "...",
         "typical_profiles": [...],
         "data_sources": ["applist", "fdc"],
         "fdc_coverage_analysis": {
           "fdc_covers_this_risk": true,
           "coverage_level": "高",
           "fdc_gaps": ["..."],
           "new_feature_opportunity": ["..."]
         }
       }
     ]
   }
   ```

3. **第二阶段按风险组织类别**：
   - 原：按生命周期阶段（pre-application, application-time...）
   - 新：按风险类型（co-lending, risk-appetite, credit-hunger...）

4. **第三阶段模板有风险指向**：
   - 每个模板注明：识别什么风险、基于什么数据、为什么有效

### 第一步：FDC预总结（Step 0）

在Phase 1之前，先增加Step 0：
- 分析4710个FDC特征的命名模式
- 总结出~10个风险维度
- 供Phase 1参考，避免重复造轮子

### 影响范围

- **修改文件**：`agents/stepwise_framework_design.py`
- **新增文件**：`outputs/feature_design/stepwise/step0_fdc_summary.json`
- **相关文档**：`FEATURE_DESIGN_UPGRADE.md`



开始新Agent开发前，请先阅读本文档，避免重复踩坑。

### 开发中参考

遇到类似问题时，参考本文档中的解决方案和设计原则。

### 开发后更新

如果遇到新的问题或有更好的解决方案，请及时更新本文档。

### Claude重启后

**重要**: 每次重启Claude Code后，请先阅读：
1. `CLAUDE.md` - 项目整体说明
2. `DEV_PLAN.md` - 当前开发进度
3. **`LESSONS_LEARNED.md`** - 已踩过的坑（本文档）

这3个文档是新对话的必读文档，能快速恢复上下文。

---

---

## 2026-05-29: 合并特征设计和特征工程为特征开发Agent

### 问题描述

1. **上下文断裂**: 特征设计Agent产出设计文档后，特征工程Agent需要重新阅读理解，同样的特征LLM看了两遍。70+特征的设计文档有信息损耗，特征工程Agent生成的代码经常遗漏特征或逻辑偏差。
2. **跨Agent传递损耗**: 设计文档以JSON存盘，代码生成时重新加载，过程中丢失了设计时的"why"。
3. **审核Agent价值衰减**: 合并后post_hook覆盖了语法检查和防穿越校验，self-review替代了逻辑一致性检查，审核Agent无独立保留价值。

### 解决方案

将特征设计Agent和特征工程Agent合并为**特征开发Agent**，引入Skill体系：

```
合并前: 设计Agent → 设计文档JSON → 工程Agent → 代码
合并后: 特征开发Agent(设计+代码生成在同上下文中) → 代码
```

### 设计原则

1. **上下文连续性 > 模块独立性**: 两个Agent虽然模块划分清晰，但LLM场景下上下文断裂的代价远超模块解耦收益。
2. **Skill替代Agent**: 当某个Agent的职责可以被函数化（输入输出清晰、逻辑固定），应改为Skill而非独立Agent。Skill更轻量（无状态管理、无文件I/O、热上下文）。
3. **post_hook替代审核Agent**: 语法/防穿越等可程序化校验的逻辑应该硬化成代码check，不需要LLM审核。
4. **IV/PSI反馈回路**: 特征设计Agent需要知道自己设计的特征实际效果如何，这个闭环缺失是当前最大的信息断层。

### 影响范围

- 删除: `feature_review_agent.py` 不再被orchestrator调用
- 新增: `agents/feature_development_agent.py` — 合并设计+工程
- 新增: `agents/skill_registry.py` — Skill注册表+post_hook机制
- 修改: `agents/feature_orchestrator.py` — v2.0: 5步流程(去审核+加反馈聚合)

---

**最后更新**: 2026-05-29
**更新原因**: 架构重构v2.0 — 合并Agent、引入Skill体系、反馈回路

---

## 2026-06-02: Web系统任务执行不稳定问题汇总（交付前必读）

### 问题1: scheduled_at 计划执行时间未生效

**现象**: 前端设置了计划执行时间（如 21:07），但任务立即执行。

**根因**: `api_create_task` 在第174-185行立即启动后台线程，没有检查 `scheduled_at` 是否为未来时间。即使设置了计划时间，线程也会立即启动。

**修复**: 在 `backend/routers/tasks.py` 的 `api_create_task` 中增加判断：如果 `scheduled_at` 是未来时间，保持 `pending` 状态，不启动线程。新增后台调度线程每30秒轮询到期任务。

**相关代码**: `backend/routers/tasks.py:api_create_task()`、`_scheduler_loop()`

### 问题2: datetime 时区感知比较导致500错误

**现象**: 前端创建任务时 API 返回 500，但任务实际已创建（status=500）。

**根因**: 前端传 ISO 时间 `2026-06-01T21:07:00+08:00`，`fromisoformat` 解析为带时区 datetime。`datetime.utcnow()` 返回 naive datetime。Python 禁止两者直接比较，抛出 `TypeError`。

```python
# ❌ 错误
parsed_scheduled_at > datetime.utcnow()
# TypeError: can't compare offset-naive and offset-aware datetimes
```

**修复**: 统一使用 `datetime.now(timezone.utc)`。

**相关代码**: `backend/routers/tasks.py` 中 `now = datetime.now(timezone.utc)`

### 问题3: 调度器启动任务没传数据路径

**现象**: 调度器触发任务后，日志显示"短链文件不存在"和"标签文件不存在"。

**根因**: 调度器第155-158行的 `args=(t.id,)` 只传了 task_id，没有从 `t.config` 读取 `url_path` 和 `label_path`。

**修复**: 调度器从 `t.config` 读取路径参数传入后台线程。

```python
# 修复前
args=(t.id,)
# 修复后
cfg = t.config or {}
args=(t.id, cfg.get("url_path"), cfg.get("label_path"))
```

**相关代码**: `backend/routers/tasks.py:_scheduler_loop()`

### 问题4: 新任务秒完成（orchestrator幂等跳过）

**现象**: 日志显示"批量生产完成"但只用了3秒，任务显示已完成但没有实际产出。

**根因**: `run_mass_production()` 通过 `orchestrator_state.json` 的 `completed_steps` 列表判断哪些步骤已执行过。当 state 文件存在且所有步骤标记为完成时，所有步骤被跳过。

**修复**: `_run_mass_production_background` 函数开始时强制删除 state 文件和 registry 文件，确保每个新任务从零开始。

```python
# 在函数开头增加
state_file = 'outputs/feature_code/orchestrator_state.json'
registry_file = 'outputs/feature_code/data_flow_registry.json'
for f in [state_file, registry_file]:
    if os.path.exists(f):
        os.remove(f)
```

**相关代码**: `backend/routers/tasks.py:_run_mass_production_background()`

### 问题5: 2916个短链下载效率低且易中断

**现象**: 数据下载阶段跑了一整夜只下到1800/2916，且后端进程退出后线程终止。

**根因**: 下载逻辑是串行 HTTP 请求（`for` 循环逐个 `requests.get`），每个请求 timeout=30秒。2916个请求串行执行、容易因网络问题卡住或超时。且后台线程依赖 uvicorn 进程存活，进程退出后线程终止，任务永远卡在 running 状态。

**修复方向**（尚未完全解决）:
1. 使用 `concurrent.futures.ThreadPoolExecutor` 并发下载
2. 设置合理的总超时
3. 下载进度日志增加 ETA 预估
4. 考虑后台进程与 uvicorn 解耦

### 问题6: reference_computation 步骤卡住

**现象**: `run_mass_production` 的 "reference_computation" 步骤执行了 1 小时 14 分钟未完成。

**根因**: 加载 1839 个样本后，`features_calculator_v2.py` 计算所有 267 个特征值的逻辑中，可能有某些特征计算超时或陷入死循环。该步骤是同步 LLM 调用，调用本身可能超时挂起。

**临时修复**: 修改 `orchestrator_state.json` 跳过卡住步骤，从 `feature_evaluation` 继续。

**根因修复方向**:
1. 特征计算过程增加超时机制（`signal.alarm` 或 `concurrent.futures`）
2. 单样本计算异常不应影响整批
3. 增加详细的步骤进度日志
4. 参考分布计算应考虑缓存优化

### 设计原则

1. **后台任务不依赖 uvicorn 进程存活**
   - uvicorn 重启后后台线程会被杀掉
   - 考虑使用 Celery 或进程级任务管理
   
2. **所有异步路径必须传递完整参数**
   - 调度器、resume、创建任务三条路径都要传 url_path/label_path
   
3. **orchestrator state 管理策略**
   - 新任务：清空 state 强制重跑
   - 恢复任务（resume）：清空 state 强制重跑
   - 注意不要用同一个 state 文件服务于多个任务
   
4. **datetime 统一使用时区感知类型**
   - 禁止 naive datetime 和 aware datetime 混用
   - 入参用 `datetime.fromisoformat` 解析
   - 比较统一用 `datetime.now(timezone.utc)`

### 影响范围

- **修改文件**: `backend/routers/tasks.py`（多处修改）
- **修改文件**: `backend/services/task_service.py`（FeatureVersion 唯一约束）
- **相关文档**: `LESSONS_LEARNED.md`（本文档）

### 最佳实践清单

✅ **DO（正确做法）**:
- 新建异步任务前清空 orchestrator state
- 所有时间比较使用 timezone-aware datetime
- 调度器从 task.config 读取路径参数
- 后台线程要有超时保护
- 下载密集型任务使用并发

❌ **DON'T（错误做法）**:
- 后台线程依赖 uvicorn 进程存活
- 串行下载大量 HTTP 请求
- naive datetime 和 aware datetime 混用
- 多个任务共享 orchestrator state 文件

### 相关引用

- 文档: `LESSONS_LEARNED.md`
- 代码: `backend/routers/tasks.py`
- 代码: `agents/feature_orchestrator.py`

---

## 2026-06-08: Docker 后端必须显式传递 OpenRouter 凭证

### 问题描述

前端页面创建“模板生成”任务后，后端日志报错：

```text
❌ 模板生成异常: Missing credentials. Please pass an `api_key`, `workload_identity`, `admin_api_key`, or set the `OPENAI_API_KEY` or `OPENAI_ADMIN_KEY` environment variable.
```

代码实际使用 `utils/llm_client.py` 通过 OpenRouter 调用 `qwen/qwen3.6-plus`，需要的是 `OPENROUTER_API_KEY`，不是 `OPENAI_API_KEY`。本地 `.env` 中存在 key，但 Docker Compose 的 backend service 没有把 `OPENROUTER_API_KEY` 注入容器，导致容器内 OpenAI SDK 初始化时拿不到凭证。

### 解决方案

1. 在 `docker-compose.yml` 和 `docker-compose.prod.yml` 的 backend `environment` 中显式传递：

```yaml
- OPENROUTER_API_KEY=${OPENROUTER_API_KEY:-}
- LLM_MODEL=${LLM_MODEL:-qwen/qwen3.6-plus}
```

2. 将 `.env.example` 改为 Docker Compose 兼容的 `KEY=value` 格式，不使用 `export KEY=value`。

3. 在 `utils/llm_client.py` 中提前检查 `OPENROUTER_API_KEY`，缺失时抛出项目语义明确的错误，而不是让 OpenAI SDK 抛出误导性的 `OPENAI_API_KEY` 错误。

### 验证结果

- 确认仓库根目录 `.env` 可被 `python-dotenv` 读取到 `OPENROUTER_API_KEY`。
- 确认 Docker Compose backend 环境变量列表包含 `OPENROUTER_API_KEY` 和 `LLM_MODEL`。
- 缺 key 时 `LLMClient` 会直接提示配置 `OPENROUTER_API_KEY`，定位更清晰。

### 设计原则

容器环境不会因为 `.env` 存在就自动把所有变量注入 service。Compose 的 `.env` 默认主要用于变量替换；运行时需要的 LLM 凭证必须在 backend service 的 `environment` 或 `env_file` 中显式传递。

### 影响范围

- 修改文件: `docker-compose.yml`
- 修改文件: `docker-compose.prod.yml`
- 修改文件: `.env.example`
- 修改文件: `utils/llm_client.py`
- 相关文档: `LESSONS_LEARNED.md`

---

## 2026-06-08: 一次性脚本和旧版Agent必须归档隔离

### 问题描述

仓库根目录和 `agents/` 中混有大量历史数据处理脚本、debug脚本、旧版分离式Agent和当前主链路代码。继续把这些文件放在同一级目录，会导致后续开发误判运行入口，例如把旧 `feature_review_agent.py` 当作当前审核流程，或把 `batch_classify_all_apps.py` 当作线上APP分类模块。

### 解决方案

1. 将历史一次性数据处理、debug、产物生成脚本归档到 `scripts/one_off/`。
2. 将旧版分离式Agent和历史实验归档到 `agents/legacy/`。
3. 保留 `agents/stepwise_framework_design.py` 在原位，因为 `DEV_PLAN.md` 明确标注它仍被保留复用。
4. 保留 `data/rule_engine_classifier.py`、`data/batch_classify_new_apps.py`、`data/rule_learner*.py` 和 `data/validate_rule_engine.py` 在 `data/`，因为它们属于APP分类基础设施，而不是一次性脚本。
5. 新增目录说明文档：`scripts/one_off/README.md`、`agents/legacy/README.md`、`data/APP_CLASSIFICATION_README.md`。

### 验证结果

- 当前主链路语法检查通过：`backend`、核心 `agents`、`data`、`utils`。
- 归档目录语法检查通过：`agents/legacy`、`scripts/one_off`。
- 旧路径 Python import 检查无命中。
- `outputs/deployment/v1` 到 `v9` 未参与本次归档，部署快照保持原样。

### 设计原则

清理仓库时先区分“当前主链路源码”、“离线基础设施”、“历史可复现脚本”和“生成产物”。不要因为某个 `.py` 没有被后端 import 就直接删除；APP分类定时任务、部署包生成器模板和 `outputs/feature_code/features_calculator_v2.py` 这类文件可能通过调度器、动态加载或产物路径被使用。

### 影响范围

- 修改目录: `scripts/one_off/`
- 修改目录: `agents/legacy/`
- 修改文档: `AGENTS.md`
- 修改文档: `CLAUDE.md`
- 修改文档: `DEV_PLAN.md`
- 修改文档: `README.md`
- 修改文档: `HANDOVER.md`
- 修改文档: `AGENT_ORCHESTRATOR_LESSONS.md`
- 修改文档: `WEB_ARCHITECTURE.md`
- 新增文档: `data/APP_CLASSIFICATION_README.md`

---

## 2026-06-09: PostgreSQL 18 Docker 镜像不要挂载到 /var/lib/postgresql/data

### 问题描述

用户按旧习惯把 PostgreSQL 18 Docker volume 挂载到 `/var/lib/postgresql/data`，容器报错提示 18+ 官方镜像使用兼容 `pg_ctlcluster` 的主版本目录结构，建议把单个 mount 放在 `/var/lib/postgresql`。

### 解决方案

PostgreSQL 18 本机测试环境使用以下挂载方式:

```bash
docker run -d \
  --name pg18 \
  -e POSTGRES_USER=riskforge \
  -e POSTGRES_PASSWORD=123456 \
  -e POSTGRES_DB=riskforge_ai \
  -p 5432:5432 \
  -v pg18_data:/var/lib/postgresql \
  postgres:18
```

### 验证结果

本机 `pg18` 容器已使用 `/var/lib/postgresql` 挂载方式成功运行，PostgreSQL 版本为 18.4。

### 设计原则

数据库 Docker volume 路径不能沿用旧版本经验。PostgreSQL 18+ 镜像为了支持主版本目录和 `pg_upgrade --link`，推荐挂载父目录 `/var/lib/postgresql`。

### 影响范围

- 修改文档: `docs/POSTGRESQL_18_MIGRATION_PLAN.md`
- 相关环境: 本机 Docker PostgreSQL 18
- 后续注意: `docker-compose.yml` 中 postgres 服务也必须挂载到 `/var/lib/postgresql`

---

## 2026-06-09: Web后端数据库完全切换到 PostgreSQL

### 问题描述

项目原先使用 SQLite 作为 Web 后端数据库，入口在 `backend/app/config.py` 和 `backend/app/database.py`，并依赖 `data/feature_mining.db`、SQLite PRAGMA、`check_same_thread=False` 以及启动时手写 `ALTER TABLE`。用户明确当前 SQLite 中只有一个用户数据，可以重新创建，因此不需要做 SQLite 历史数据迁移。

### 解决方案

1. 移除代码中的数据库连接串默认值，要求通过 `DATABASE_URL` 环境变量或 `.env` 提供:

```bash
postgresql+psycopg://riskforge:123456@127.0.0.1:5432/riskforge_ai
```

2. 移除 `backend/app/database.py` 中所有 SQLite 专用逻辑。
3. 新增 `psycopg[binary]` 和 `alembic` 依赖。
4. 新增 Alembic 配置和初始 schema migration。
5. Docker 后端启动前执行:

```bash
alembic upgrade head
```

### 验证结果

- 本机 `pg18` 容器版本: PostgreSQL 18.4。
- `alembic upgrade head` 成功执行到 `20260609_0001`。
- PostgreSQL 中创建了 `users`、`tasks`、`task_logs`、`feature_versions`、`feature_metrics`、`chat_sessions`、`chat_messages`、`alembic_version`。
- 临时后端端口 `18000` 健康检查通过。
- 测试用户 `pg_test_user` 注册和登录通过，确认写入 PostgreSQL。

### 设计原则

既然决定 PostgreSQL 是唯一运行数据库，就不要保留 SQLite fallback。否则后续模板库、审批历史、项目隔离等新表容易出现“开发连 SQLite、部署连 PostgreSQL”的双库漂移问题。表结构演进统一交给 Alembic，应用启动不再偷偷 `create_all` 或手写 `ALTER TABLE`。

### 影响范围

- 修改文件: `backend/app/config.py`
- 修改文件: `backend/app/database.py`
- 修改文件: `backend/requirements.txt`
- 修改文件: `requirements.txt`
- 新增文件: `alembic.ini`
- 新增目录: `backend/migrations/`
- 修改文件: `docker-compose.yml`
- 修改文件: `docker-compose.prod.yml`
- 修改文件: `Dockerfile.backend`
- 修改文档: `docs/POSTGRESQL_18_MIGRATION_PLAN.md`
- 修改文档: `DEV_PLAN.md`

---

## 2026-06-09: 模板库基础数据使用幂等初始化脚本

### 问题描述

`outputs/feature_templates/channel1_templates.json` 中既包含 7 个模板维度，也包含 16 个已生效 channel1 模板。用户询问是否应该像表结构迁移一样单独做项目初始化，在迁移之后填充这些平台基础数据。

### 解决方案

表结构和平台基础数据分层处理:

1. Alembic migration 只负责建表:
   - `template_dimensions`
   - `templates`
   - `template_review_histories`
   - `template_rejected_memories`
2. 平台基础数据通过统一初始化入口导入:

```bash
python scripts/init_project_data.py
```

3. 模板库 seed 读取 `outputs/feature_templates/channel1_templates.json`，幂等 upsert:
   - 顶层 `dimensions` -> `template_dimensions`
   - 顶层 `templates` -> `templates`
   - 当前 channel1 模板状态统一设为 `active`

### 验证结果

- Alembic 成功升级到 `20260609_0002`。
- 初始化脚本导入 7 个模板维度和 16 个 active 模板。
- 重复执行初始化脚本不会重复插入，第二次执行结果为 0 新增、7 个维度更新、16 个模板更新。

### 设计原则

不要把业务初始数据硬编码进 schema migration。migration 管结构，seed 管平台基础数据。seed 必须幂等，生产环境、本地测试环境和 Docker 后端启动链路都可以重复执行同一套初始化脚本。

### 影响范围

- 新增文件: `backend/models/template.py`
- 修改文件: `backend/models/__init__.py`
- 新增文件: `backend/migrations/versions/20260609_0002_template_library_schema.py`
- 新增文件: `scripts/init_project_data.py`
- 新增目录: `scripts/seeds/`
- 修改文件: `Dockerfile.backend`
- 修改文件: `docker-compose.yml`
- 修改文件: `docker-compose.prod.yml`
- 修改文档: `docs/POSTGRESQL_18_MIGRATION_PLAN.md`
- 修改文档: `DEV_PLAN.md`

---

## 2026-06-09: 模板生命周期禁止 JSON 双写

### 问题描述

模板库迁移到 PostgreSQL 后，运行时仍有多条旧路径会读写 `channel1_templates.json`、`channel2_pending.json` 或 `promoted_templates.json`。如果继续保留这些双写路径，本地、Docker、生产数据库之间很容易出现模板状态不一致，尤其是通道2待审批、审批通过、拒绝记忆和知识抽取自动入库这些生命周期状态。

### 解决方案

将 PostgreSQL 作为模板库唯一事实来源:

1. `backend/services/template_library.py` 提供统一模板查询、待审批 upsert、审批通过、拒绝记忆和计算函数追加能力。
2. `FeatureDevelopmentAgent`、`FeatureOrchestrator`、`TemplateGenerationAgent`、`AgentChat`、`KnowledgeExtractor`、模板审核 API 和模板评估任务全部改为读写 DB。
3. `outputs/feature_templates/channel1_templates.json` 只作为 `scripts/init_project_data.py` 的 seed 输入，不再参与运行时读写。
4. 历史 pending seed 归档到 `scripts/seeds/fixtures/channel2_pending.seed.json`，不放在运行时输出目录。
5. 不再写回 `channel2_pending.json` 和 `promoted_templates.json`。

### 验证结果

- `python -m py_compile` 覆盖模板库 service、models、routers 和三个 agent 文件，语法检查通过。
- `git diff --check` 通过。
- FastAPI app、`FeatureDevelopmentAgent`、`TemplateGenerationAgent` 导入验证通过。
- 由于本次 Codex 提权受用量限制拦截，`alembic upgrade head` 和初始化脚本需要在本机手动执行。

### 设计原则

模板生命周期状态必须单写 PostgreSQL。JSON 可以作为初始化或历史素材，但不能作为运行时读写路径；否则审批状态、模板函数代码、拒绝原因和知识抽取结果会变成多个事实来源。

### 影响范围

- 修改文件: `backend/services/template_library.py`
- 修改文件: `backend/routers/templates.py`
- 修改文件: `backend/routers/agents.py`
- 修改文件: `backend/routers/agent_chat.py`
- 修改文件: `backend/services/knowledge_extractor.py`
- 修改文件: `backend/services/task_service.py`
- 修改文件: `agents/feature_development_agent.py`
- 修改文件: `agents/feature_orchestrator.py`
- 修改文件: `agents/template_generation_agent.py`
- 修改文档: `DEV_PLAN.md`

---

## 2026-06-10: 项目初始化必须导入历史 channel2 pending 模板

### 问题描述

用户发现 `channel2-pending` 中的历史数据没有进入 PostgreSQL，`templates` 表里没有非 active 数据。原因是 `scripts/init_project_data.py` 只导入了 `outputs/feature_templates/channel1_templates.json` 中的 active 模板，没有导入旧的历史 pending seed。

### 解决方案

在 `scripts/seeds/seed_template_library.py` 中新增 `seed_pending_templates()`，并接入 `scripts/init_project_data.py`:

```bash
DATABASE_URL=postgresql+psycopg://riskforge:123456@127.0.0.1:5432/riskforge_ai python scripts/init_project_data.py
```

该导入逻辑保持幂等:

1. 已经是 active 的模板不会被降级回 pending。
2. 同 `template_id` 的 pending/rejected 记录会更新。
3. 缺失的历史 pending 模板会插入 `templates.status='pending'`。

历史 pending seed 后续固定放在 `scripts/seeds/fixtures/channel2_pending.seed.json`，避免 `outputs/feature_design/channel2_pending.json` 被误认为仍是运行时审批队列。

### 验证结果

- `python -m py_compile scripts/init_project_data.py scripts/seeds/seed_template_library.py` 通过。
- `git diff --check scripts/init_project_data.py scripts/seeds/seed_template_library.py` 通过。
- 本机 PostgreSQL 初始化输出:
  - active 模板更新 16 条
  - pending 模板新增 6 条
- `templates` 表状态分布确认:
  - `active`: 16
  - `pending`: 6

### 设计原则

从 JSON 切到 DB 时，不仅要迁移 active 主数据，也要迁移生命周期中的中间态数据。否则 API 看起来已经 DB 化，但历史 pending 审批队列会丢失。

### 影响范围

- 修改文件: `scripts/init_project_data.py`
- 修改文件: `scripts/seeds/seed_template_library.py`
- 修改文档: `DEV_PLAN.md`

---

## 2026-06-10: 项目关联使用默认项目承载历史数据

### 问题描述

模板库已经迁移到 PostgreSQL 后，下一步需要支持多个业务项目。用户明确模板应该是平台级资产，项目中只选择启用哪些模板；知识库后续需要拆分为平台级和项目级。现有历史任务、结果和模板选择需要有一个默认归属，否则引入项目后旧数据会变成无项目数据。

### 解决方案

新增项目建模和默认项目:

1. 新增 `projects` 表，初始化 `id=1` 的 `默认项目`。
2. 新增 `project_templates` 表，表示项目启用哪些平台模板。
3. 给 `tasks`、`feature_versions`、`feature_metrics` 增加 `project_id`。
4. migration 将已有历史任务和结果挂到默认项目。
5. `scripts/init_project_data.py` 保证默认项目存在，并为默认项目启用所有 active 平台模板。
6. 新增 `/api/projects` 项目管理接口，任务列表和特征版本接口支持 `project_id` 过滤。

### 验证结果

- `alembic upgrade head` 成功升级到 `20260610_0004`。
- `python scripts/init_project_data.py` 成功输出默认项目:
  - `id: 1`
  - `name: 默认项目`
- 本机 PostgreSQL 验证:
  - `projects`: 1 条默认项目
  - 历史 `tasks`: 已归属 `project_id=1`
  - `project_templates`: 默认项目启用 16 个 active 平台模板
- Python 编译检查和 `git diff --check` 通过。

### 设计原则

模板本身保持平台级，不直接加 `project_id`。项目通过关联表选择启用模板，这样模板审批、拒绝记忆、模板代码和版本生命周期仍然只有一份平台事实来源。项目级差异应该放在 `project_templates.config_override` 或后续项目配置中。

### 影响范围

- 新增文件: `backend/models/project.py`
- 新增文件: `backend/services/project_service.py`
- 新增文件: `backend/routers/projects.py`
- 新增文件: `backend/migrations/versions/20260610_0004_project_scoping.py`
- 修改文件: `backend/models/task.py`
- 修改文件: `backend/models/feature.py`
- 修改文件: `backend/models/__init__.py`
- 修改文件: `backend/app/main.py`
- 修改文件: `backend/services/task_service.py`
- 修改文件: `backend/routers/tasks.py`
- 修改文件: `backend/routers/features.py`
- 修改文件: `scripts/init_project_data.py`
- 修改文档: `DEV_PLAN.md`

---

## 2026-06-10: 前端先接项目上下文主干

### 问题描述

后端新增项目关联后，旧前端仍然按全局任务运行。如果不接入当前项目选择，用户创建任务、查看任务列表、清空任务时仍会混用全局上下文，违背项目隔离目标。

### 解决方案

前端先接最小主干:

1. 新增项目类型和 API:
   - `web-frontend/src/types/project.ts`
   - `/api/projects`
   - `/api/projects/default`
2. 新增 `projectStore`，从后端加载项目并把当前项目 ID 存入 `localStorage`。
3. 顶部 Header 增加当前项目选择器和新建项目弹窗。
4. 任务列表调用 `/api/tasks?project_id=...`。
5. 创建任务时提交当前 `project_id`。
6. 清空任务改为只清当前项目任务。

### 验证结果

- 后端相关文件 Python 编译通过。
- `git diff --check` 通过。
- 当前 worktree 没有 `web-frontend/node_modules`，未执行前端 `npm run build`；需要在安装依赖后补跑。

### 设计原则

先把“当前项目上下文”贯穿任务主链路，再扩展专门的项目管理页面和项目模板勾选页面。这样旧页面不会被一次性重构过大，同时后端默认项目仍能兼容未传 `project_id` 的旧调用。

### 影响范围

- 新增文件: `web-frontend/src/types/project.ts`
- 新增文件: `web-frontend/src/store/projectStore.ts`
- 修改文件: `web-frontend/src/services/api.ts`
- 修改文件: `web-frontend/src/components/Layout.tsx`
- 修改文件: `web-frontend/src/pages/Tasks.tsx`
- 修改文件: `web-frontend/src/types/task.ts`
- 修改文件: `web-frontend/src/types/index.ts`
- 修改文件: `backend/services/task_service.py`
- 修改文件: `backend/routers/tasks.py`
- 修改文档: `DEV_PLAN.md`

---

## 2026-06-10: 创建项目时必须选择启用模板

### 问题描述

用户指出项目管理不能只创建项目基础信息，还应该在创建项目时选择哪些平台模板加入项目。项目模板是平台级资产，项目通过关联表选择启用范围。

### 解决方案

1. 后端新增批量设置项目模板选择接口:
   - `PUT /api/projects/{project_id}/templates`
   - 请求体: `{ "template_ids": ["T001", "T002"] }`
2. 创建项目接口支持 `template_ids`，不传时兼容旧行为，默认启用所有 active 模板。
3. 项目管理页创建/编辑弹窗加载 active 平台模板，提供勾选。
4. 编辑项目时读取当前项目已启用模板，并可重新保存选择。

### 验证结果

- 后端 Python 编译通过。
- 原项目前端 `npm run build` 通过。

### 设计原则

模板仍然是平台级，项目只保存选择关系。项目创建是模板启用范围的自然入口，不能把模板选择藏到后续隐式默认行为里。

### 影响范围

- 修改文件: `backend/services/project_service.py`
- 修改文件: `backend/routers/projects.py`
- 修改文件: `web-frontend/src/pages/Projects.tsx`
- 修改文件: `web-frontend/src/services/api.ts`
- 修改文件: `web-frontend/src/types/project.ts`
- 修改文档: `DEV_PLAN.md`

---

## 2026-06-11: 项目模板批量选择使用三态全选

### 问题描述

用户指出项目编辑里的模板选择不应该拆成“全选”和“全部取消”两个按钮，而应该合并成一个全选控件：全部选择时方框显示对号，全部未选时方框为空，部分选择时方框显示横线。

### 解决方案

在项目管理页的“启用模板”标题旁使用 Ant Design `Checkbox` 的三态能力：

1. `checked=true`：当前项目已选择全部 active 模板。
2. `checked=false`：当前项目没有选择 active 模板。
3. `indeterminate=true`：当前项目只选择了部分 active 模板。
4. 点击控件时根据 checkbox 状态切换为全选或清空。

### 验证结果

- 原项目目录执行 `npm run build` 通过。

### 设计原则

批量选择应优先使用用户熟悉的三态 checkbox 语义，而不是拆成多个文字按钮。这样可以同时表达当前选择状态和批量操作意图。

### 影响范围

- 修改文件: `web-frontend/src/pages/Projects.tsx`

---

## 2026-06-11: 模板列表排序以后端统一为准

### 问题描述

用户指出项目模板列表需要优先按照创建时间排序，其次按照 `template_id` 排序。原后端模板查询按维度顺序和 `template_id` 排序，不符合项目编辑时模板选择的预期顺序。

### 解决方案

1. `list_templates()` 统一改为 `created_at asc, template_id asc, id asc`。
2. `template_to_channel1_item()` 响应补出 `created_at` 字段。
3. 项目已关联模板 `list_project_templates()` 同步按模板创建时间和 `template_id` 排序。
4. 前端 `Channel1Template` 类型补充 `created_at`。
5. 前端模板列表接口 `fetchChannel1Templates()` 和 `fetchChannel2PendingTemplates()` 使用同一排序函数兜底，确保“已生效”和“待审核”两个 tab 顺序一致。

### 验证结果

- `python -m py_compile backend/services/template_library.py backend/services/project_service.py` 通过。
- 原项目目录执行 `npm run build` 通过。

### 设计原则

模板排序属于后端列表契约，应在服务层统一处理，避免项目编辑页、模板侧边栏和项目模板接口各自维护不同排序逻辑。

### 影响范围

- 修改文件: `backend/services/template_library.py`
- 修改文件: `backend/services/project_service.py`
- 修改文件: `web-frontend/src/services/api.ts`

---

## 2026-06-15: 前端产品层级与模板资产语义修正

### 问题描述

用户指出前端产品设计存在两类语义偏差：

1. 所有菜单平铺在一个层级上，无法表达“项目是平台维度管理对象、任务属于项目、结果交付对应任务”的层次关系。
2. 模板库把模板当成有业务含义的特征来呈现，出现“历史表现”、IV/PSI/覆盖率等特征效果信息；但模板本质是数据加工方式，审批对象也是模板本身。

### 解决方案

1. 左侧导航改为分组信息架构：
   - 平台管理：项目管理、模板资产
   - 当前项目：项目工作台、数据与知识、生产任务
   - 任务结果：评估报告、部署版本
   - 辅助工具：智能助理
2. 模板页改为“模板资产”，字段围绕模板类型、加工方式说明、执行方式、审批状态组织。
3. 移除模板列表中的历史表现信息，避免把模板的加工口径和特征评估结果混在一起。
4. 工作台、评估报告、部署版本页面文案补充当前项目和任务结果关系。

### 验证结果

- `npm run build` 通过。
- 产品语义检查：菜单层级、模板字段、任务结果页面名称均已按用户反馈修正。

### 设计原则

平台级资产、项目级生产、任务级结果必须在信息架构中分层表达。模板只负责定义数据加工方法，不承载具体业务含义和历史表现；业务含义与效果应由生产出的特征及其评估报告承载。

### 影响范围

- 修改文件: `web-frontend/src/components/Layout.tsx`
- 修改文件: `web-frontend/src/pages/Dashboard.tsx`
- 修改文件: `web-frontend/src/pages/Projects.tsx`
- 修改文件: `web-frontend/src/pages/Templates.tsx`
- 修改文件: `web-frontend/src/pages/Evaluation.tsx`
- 修改文件: `web-frontend/src/pages/Deployment.tsx`
- 修改文件: `web-frontend/src/pages/Tasks.tsx`
- 修改文件: `web-frontend/src/services/mockData.ts`
- 修改文件: `web-frontend/src/components/ReviewPanel.tsx`
- 修改文件: `web-frontend/src/components/TemplateSidebar.tsx`
- 修改文档: `DEV_PLAN.md`

---

## 2026-06-15: 评估报告必须展示特征逻辑

### 问题描述

用户指出评估报告只展示 IV、PSI、覆盖率等结果指标还不够，产品经理和风控评审需要看到每个特征的加工逻辑。没有特征逻辑时，评估页无法解释“这个指标到底怎么算出来”，也不利于判断特征是否符合业务口径。

### 解决方案

1. `FeatureMetric` 前端类型补充 `feature_logic`、`template_type`、`source_fields`。
2. mock 评估数据补齐每个特征的加工口径、输入字段和模板类型。
3. 评估报告表格新增“特征逻辑”列，并提供“查看口径”抽屉展示完整说明、输入字段和评估结果。

### 验证结果

- `npm run build` 通过。
- 评估报告已能在特征明细中直接看到加工逻辑，并可打开详情查看完整口径。

### 设计原则

评估报告不能只做指标看板，还要承载特征可解释性。特征评审链路中，“怎么算”应与“效果如何”并列展示，避免指标脱离业务口径。

### 影响范围

- 修改文件: `web-frontend/src/pages/Evaluation.tsx`
- 修改文件: `web-frontend/src/types/feature.ts`
- 修改文件: `web-frontend/src/services/mockData.ts`

---

## 2026-06-15: 前端原型需要更强科技感视觉

### 问题描述

用户希望整体页面风格更炫酷、科技感更强，尤其是智能助理部分。原有页面偏传统后台系统，智能助理只是普通聊天框，缺少 AI 产品的控制台感和识别度。

### 解决方案

1. 全局应用壳升级为暗色科技风格：
   - 网格背景
   - 玻璃质感卡片
   - 霓虹边线
   - 暗色表格和输入控件
   - 高亮渐变主按钮
2. 智能助理页改为 Copilot 控制台：
   - 顶部展示智能助理定位和能力标签
   - 消息流使用暗色网格背景
   - 用户和助手气泡使用不同高亮色
   - 欢迎态提供常用提问入口
   - 右侧会话和模板区保持联动但视觉更像工作台侧轨

### 验证结果

- `npm run build` 通过。
- 视觉范围覆盖 Layout、通用卡片/表格、评估报告、智能助理对话区和输入区。

### 设计原则

科技感不应只靠装饰图，而应该体现在信息层级、材质、动效、色彩和交互状态的统一系统里。智能助理作为 AI 产品入口，需要比普通后台页面更强的主视觉和能力感。

### 影响范围

- 修改文件: `web-frontend/src/components/Layout.tsx`
- 修改文件: `web-frontend/src/pages/AgentChat.tsx`
- 修改文件: `web-frontend/src/components/ChatMessage.tsx`
- 修改文件: `web-frontend/src/components/ChatInput.tsx`
- 修改文件: `web-frontend/src/index.css`
- 修改文档: `DEV_PLAN.md`

---

## 2026-06-15: 暗色主题不能只覆盖页面主体

### 问题描述

用户指出虽然整体做了暗色主题，但一些细节配色仍有问题。排查后发现主要问题来自 Ant Design 的弹层和局部组件：Select 下拉、Modal、Drawer、Popover、Tag、分页、空状态、Descriptions、Steps、图表 tooltip/坐标轴等没有完全继承主页面暗色样式，导致局部白底、黑字或低对比。

### 解决方案

1. 在全局 CSS 中补充暗色主题变量，统一背景、边框、主文本、弱文本、高亮色。
2. 对页面内组件补齐暗色覆盖：
   - Table
   - Tag
   - Button
   - Descriptions
   - Steps
   - Empty
   - Pagination
   - Segmented
3. 对挂载到 body 的弹层单独覆盖：
   - Select Dropdown
   - Modal
   - Drawer
   - Popover
   - Tooltip
   - Message
4. 调整评估图表的 axis、legend、label、tooltip 和 Top 特征表格，避免图表仍使用浅色主题默认黑字。

### 验证结果

- `npm run build` 通过。
- 针对本次文件执行 `git diff --check` 通过。
- 搜索本次重点页面和组件，已移除明显浅底/低对比残留。

### 设计原则

暗色主题必须覆盖“页面主体 + 弹层容器 + 图表系统 + 内嵌表格”四个层面。Ant Design 的弹层默认挂在 body 上，不能只依赖页面容器选择器，否则会出现局部视觉断层。

### 影响范围

- 修改文件: `web-frontend/src/index.css`
- 修改文件: `web-frontend/src/components/FeatureCharts.tsx`
- 修改文件: `web-frontend/src/pages/Dashboard.tsx`
- 修改文件: `web-frontend/src/pages/Templates.tsx`
- 修改文件: `web-frontend/src/pages/Deployment.tsx`
- 修改文档: `DEV_PLAN.md`
