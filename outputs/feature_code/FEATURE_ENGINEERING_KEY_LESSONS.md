# 特征工程关键经验总结（2026-05-04）

本文档记录特征工程开发中遇到的关键问题和解决方案，供后续开发参考，避免重复踩坑。

---

## 1. 特征计算代码必须动态适配特征设计

### 问题描述

**现象**: 第一次生成的特征计算代码中，LLM"想象"出很多不存在的字段（如`gambling_count`, `total_installed_apps`等）。

**根本原因**: 
- 特征工程Agent应该根据**特征设计文档**（feature_design_doc.json）动态生成代码
- 每个特征的`calculation_logic`字段告诉Agent如何计算
- Agent需要读取这个字段，生成对应的Python代码

### 解决方案

**正确做法**:
```python
# 在FeatureEngineeringAgent中
def _build_prompt(self):
    for feature in self.features:
        prompt += f"- {feature['feature_name']}: {feature['calculation_logic']}\n"
```

**示例**：
```
Feature: ratio_applist_highrisk_apps_all
Logic: (count(gambling)+count(cash_loan)+...) / total_apps

生成的代码应该是：
high_risk_count = sum(cat_counts.get(c, 0) for c in ['gambling', 'cash_loan', ...])
features['ratio_applist_highrisk_apps_all'] = high_risk_count / total_apps
```

### 经验教训

✅ **DO**:
- 从特征设计文档读取每个特征的`calculation_logic`
- 根据`calculation_logic`生成对应的Python代码
- 代码是"动态模板"，不是硬编码

❌ **DON'T**:
- 假设所有特征都有相同的结构
- 凭空想象数据字段
- 硬编码特征计算逻辑

---

## 2. 应用分类必须来源于分类结果（禁止硬编码）

### 问题描述

**现象**: 第一次生成的代码中硬编码了类别集合：
```python
STANDARD_CATEGORIES = {
    'gambling', 'cash_loan', 'fintech_lending', ...
}
```

**问题**:
- 容易与分类结果不一致（如果重新分类，类别变化了）
- 需要维护两处代码
- 违反单一数据源原则

### 解决方案

**动态提取类别**:
```python
def _extract_standard_categories(self) -> set:
    """从app_classification_cache中提取所有唯一类别"""
    categories = set()
    for pkg_info in self.app_classification_cache.values():
        category = pkg_info.get('category', 'other')
        if category:
            categories.add(category)
    return categories if categories else {'other'}
```

**使用动态类别**:
```python
# ❌ 硬编码
standard_cats = STANDARD_CATEGORIES

# ✅ 动态提取
standard_cats = self.standard_categories
```

### 经验教训

✅ **DO**:
- 所有类别都从`app_classification_cache`提取
- 单一数据源：`outputs/app_analysis/classification_complete_11850.json`
- 自动同步：重新分类后，特征计算器自动适配

❌ **DON'T**:
- 硬编码类别名称
- 在多处维护类别列表
- 假设类别永远不变

---

## 3. 防穿越时间过滤（核心原则）

### 问题描述

**现象**: 
- applist只过滤了`inTime`，没有过滤`upTime`
- 导致申请后更新的应用也被计入

**根本原因**:
- 申请时间（applyTime）是防穿越的基准点
- 所有特征计算只能使用申请时间之前的数据

### 正确实现

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
    if l.get('tgl_penyaluran_dana') and datetime.strptime(l['tgl_penyaluran_dana'], '%Y-%m-%d').date() >= cutoff_30d
]
```

### 经验教训

✅ **DO**:
- applyTime是唯一可信的防穿越基准点
- applist同时检查inTime和upTime
- FDC检查放款日期（tgl_penyaluran_dana）
- 时间窗口从apply_time往前推

❌ **DON'T**:
- 使用当前系统时间（datetime.now()）
- 只检查inTime不检查upTime
- 假设所有数据的日期都<=apply_time

---

## 4. FDC特定数据结构

### 问题描述

**现象**: 首次尝试时使用了错误的字段名：
```python
# ❌ 字段不存在
inquiry.get('last_3days', 0)
inquiry.get('last_7days', 0)
platform_aktif.get('count', 0)
```

### 实际数据结构

**history_inquiry完整结构**:
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
  },
  "last3DaysInquiry": [
    {
      "hit_by": "KREDINESIA",
      "jml_data": 25,
      "tgl_inquiry": "2026-03-08 15:32:23"
    },
    ...
  ]
}
```

**platform_aktif完整结构**:
```json
{
  "jumlahPlatformAktif": 4,  // 活跃平台数
  "platform": [
    "AFDC241",
    "AFDC253",
    "AFDC183",
    "AFDC233"
  ]
}
```

**pinjaman关键字段**:
```json
{
  "tgl_penyaluran_dana": "2026-01-20",  // 放款日期
  "nilai_pendanaan": 1000000,           // 贷款金额
  "sisa_pinjaman_berjalan": 1000000,    // 未还余额
  "dpd_max": 0,                         // 最大逾期天数
  "status_pinjaman": "O",              // Outstanding/Closed
  "id_penyelenggara": "AFDC241"       // 平台ID
}
```

### 正确代码

```python
# ✅ 正确的字段提取
fdc_stat = fdc.get('history_inquiry', {}).get('statistic', {})
q3d = fdc_stat.get('3_hari', 0)
q7d = fdc_stat.get('7_hari', 0)
q30d = fdc_stat.get('30_hari', 0)

active_plat = fdc.get('platform_aktif', {}).get('jumlahPlatformAktif', 0)

for loan in fdc['pinjaman']:
    disburse_str = loan.get('tgl_penyaluran_dana', '')
    amount = loan.get('nilai_pendanaan', 0)
    balance = loan.get('sisa_pinjaman_berjalan', 0)
    dpd = loan.get('dpd_max', 0)
    platform_id = loan.get('id_penyelenggara', '')
```

### 经验教训

✅ **DO**:
- 实际查看原始JSON数据确认字段名
- 使用`statistic`获取各时间窗口查询数
- 使用`jumlahPlatformAktif`获取活跃平台数
- 遍历`pinjaman[]`进行统计

❌ **DON'T**:
- 假设字段名（如'last_3days'）
- 假设存在计数值字段
- 不验证数据结构

---

## 5. 所有特征必须从原始数据计算（无假设字段）

### 问题描述

**现象**: 第一次生成的代码假设了很多字段：
```python
# ❌ 原始数据中不存在这些字段
gambling = data.get('gambling_count', 0)
total_apps = data.get('total_installed_apps', 0)
dpd_90plus = data.get('loans_dpd_gt_90_count', 0)
```

**问题**:
- 原始JSON中没有这些预计算的字段
- 需要实时计算（遍历applist、pinjaman等）

### 正确的计算方式

**applist特征计算**:
```python
# ✅ 从原始数据开始计算
filtered_applist = self._filter_applist(data, apply_time_dt)

# 1. 对每个应用分类
app_categories = {}
for app in filtered_applist:
    pkg = app.get('packageX', '')
    if pkg in self.app_classification_cache:
        category = self.app_classification_cache[pkg].get('category', 'other')
        app_categories[pkg] = category

# 2. 统计各类别数量
cat_counts = {}
for cat in app_categories.values():
    cat_counts[cat] = cat_counts.get(cat, 0) + 1

# 3. 计算特征
total_apps = len(filtered_applist)
high_risk_count = sum(cat_counts.get(c, 0) for c in ['gambling', 'cash_loan', ...])
features['ratio_applist_highrisk_apps_all'] = high_risk_count / total_apps
```

**FDC特征计算**:
```python
# ✅ 遍历pinjaman列表进行统计
pinjaman = fdc.get('pinjaman', [])

# 统计DPD>90的笔数
dpd_90plus = sum(1 for l in pinjaman if l.get('dpd_max', 0) > 90)

# 统计总金额
total_amount = sum(l.get('nilai_pendanaan', 0) for l in pinjaman)

# 平均金额
avg_amount = total_amount / len(pinjaman) if pinjaman else 0
```

### 经验教训

✅ **DO**:
- 从原始JSON字段开始（appList、pinjaman等）
- 实时遍历和计算
- 使用分类cache推导特征

❌ **DON'T**:
- 假设存在预计算的字段
- 跳过数据预处理步骤
- 直接使用计数值

---

## 6. 额外经验：代码质量

### 防穿越机制是核心
- 所有特征计算前必须先过滤数据
- applyTime是唯一的基准点
- 任何使用未来数据的特征都是无效的

### 异常处理
- 安全除法（除0返回0）
- 日期格式错误处理
- 缺失字段处理

### 代码规范
- 中文注释说明业务逻辑
- 每个特征独立函数
- 返回统一格式（dict）

---

## 检查清单

在开发新的特征计算代码时，请检查：

- [ ] 从原始数据开始（appList、pinjaman等）
- [ ] 使用分类cache动态提取类别
- [ ] applist同时过滤inTime和upTime
- [ ] FDC过滤放款日期
- [ ] 时间窗口从apply_time往前推
- [ ] 所有字段名都已在原始JSON中验证
- [ ] 处理所有除0情况
- [ ] 处理日期格式错误
- [ ] 中文注释清晰
- [ ] 代码可以动态适配不同的特征设计

---

## 相关引用

- 特征设计文档: `outputs/feature_design/feature_design_doc.json`
- 特征计算代码: `outputs/feature_code/features_calculator_v2.py`
- 改进总结: `outputs/feature_code/FEATURE_CALCULATOR_V2_IMPROVEMENTS.md`
- LESSONS_LEARNED主文档: `LESSONS_LEARNED.md`
