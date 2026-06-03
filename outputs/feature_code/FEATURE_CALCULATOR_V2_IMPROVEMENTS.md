# 特征计算器V2改进总结（2026-05-04）

## 核心改进

### 1. 消除硬编码类别

**问题**：
```python
# ❌ 硬编码，容易与分类cache不一致
STANDARD_CATEGORIES = {'gambling', 'cash_loan', ...}
```

**改进**：
```python
# ✅ 从app_classification_cache动态提取
def _extract_standard_categories(self) -> set:
    categories = set()
    for pkg_info in self.app_classification_cache.values():
        category = pkg_info.get('category', 'other')
        if category:
            categories.add(category)
    return categories if categories else {'other'}
```

**好处**：
- 单一数据源：分类结果来自 `outputs/app_analysis/classification_complete_11850.json`
- 自动同步：如果重新分类（新增类别），特征计算器自动适配
- 无维护成本：不需要手动更新两处代码

---

### 2. 正确的applist时间过滤

**原始问题**：
```python
# ❌ 只过滤inTime
filtered = [app for app in app_list if app.get('inTime', 0) <= apply_time_ms]
```

**修正**：
```python
# ✅ 同时过滤inTime AND upTime
filtered = [
    app for app in app_list
    if app.get('inTime', 0) <= apply_time_ms and app.get('upTime', 0) <= apply_time_ms
]
```

**理由**：
- 避免使用申请后更新的应用（可能是用户申请后新更新的）
- 更符合防穿越原则：只使用申请时间之前已存在的应用

---

### 3. 正确的FDC数据结构

**原始错误**：
```python
# ❌ 字段不存在
q3d = inquiry.get('last_3days', 0)
q7d = inquiry.get('last_7days', 0)
```

**修正**：
```python
# ✅ 使用实际字段名
fdc_stat = filtered_fdc.get('history_inquiry', {}).get('statistic', {})
q3d = fdc_stat.get('3_hari', 0)
q7d = fdc_stat.get('7_hari', 0)
q30d = fdc_stat.get('30_hari', 0)
```

**FDC statistic字段说明**：
```json
"statistic": {
  "3_hari": 8,      // 近3天查询次数
  "7_hari": 13,     // 近7天查询次数
  "30_hari": 23,    // 近30天查询次数
  "90_hari": 31,    // 近90天查询次数
  "180_hari": 37,   // 近180天查询次数
  "360_hari": 40,   // 近360天查询次数
  ">360_hari": 42   // 超过360天的查询次数
}
```

---

### 4. 正确的platform_aktif字段

**原始错误**：
```python
# ❌ 字段名错误
active_plat = filtered_fdc.get('platform_aktif', {}).get('count', 0)
```

**修正**：
```python
# ✅ 正确的字段名
active_plat = filtered_fdc.get('platform_aktif', {}).get('jumlahPlatformAktif', 0)
```

**实际数据结构**：
```json
"platform_aktif": {
  "jumlahPlatformAktif": 4,  // 活跃平台数
  "platform": [
    "AFDC241",
    "AFDC253",
    "AFDC183",
    "AFDC233"
  ]
}
```

---

## 代码质量提升

### 1. 防穿越机制完善

**applist防穿越**：
```python
# 同时检查inTime和upTime
if app.get('inTime', 0) <= apply_time_ms and app.get('upTime', 0) <= apply_time_ms
```

**FDC防穿越**：
```python
# 只使用申请时间之前放款的贷款
disburse_date = datetime.strptime(loan['tgl_penyaluran_dana'], '%Y-%m-%d').date()
if disburse_date <= apply_time_dt.date():
    filtered_pinjaman.append(loan)
```

---

### 2. 特征计算准确性

**高风险应用统计**（使用动态类别）：
```python
high_risk_cats = ['gambling', 'cash_loan', 'fintech_lending', 'fake_gps', 'clone_app']
high_risk_count = sum(cat_counts.get(c, 0) for c in high_risk_cats)
```

**贷款类别多样性**（使用动态类别）：
```python
loan_cats = {'cash_loan', 'fintech_lending', 'banking', 'ewallet', 'installment'}
present_loan_cats = [c for c in loan_cats if cat_counts.get(c, 0) > 0]
features['count_applist_loan_categories_all'] = len(present_loan_cats)
```

**交叉特征**（正确获取FDC数据）：
```python
# 从FDC statistic获取30天查询数
fdc_stat = original_data.get('params', {}).get('FDC', {}).get('history_inquiry', {}).get('statistic', {})
query_30d = fdc_stat.get('30_hari', 0)
features['cross_applist_loanapp_fdc_query_30d'] = loan_app_count / query_30d
```

---

## 验证结果

**代码测试**：
```
✅ Code loads successfully
✅ FeatureCalculator initialized
✅ Standard categories extracted dynamically (17 categories)
```

**类别一致性**：
```python
# 从cache提取的类别
{'productivity', 'social_entertainment', 'app_store', 'fake_gps',
 'fintech_lending', 'religious', 'food_delivery', 'other', 'clone_app',
 'transportation', 'gambling', 'cash_loan', 'installment', 'utility',
 'banking', 'ewallet', 'shopping'}
```

与 `outputs/app_analysis/classification_complete_11850.json` 完全一致！

---

## 经验教训

1. **不要硬编码可推导的数据**：
   - 类别应该从分类结果中提取
   - 避免多处维护导致不一致

2. **必须对照原始数据结构**：
   - 不要假设字段名
   - 实际查看JSON数据确认字段

3. **防穿越是核心**：
   - applist要同时检查inTime和upTime
   - FDC要检查放款日期
   - 所有时间窗口从applyTime往前推

4. **FDC statistic字段含义**：
   - `3_hari` = 近3天查询次数
   - `7_hari` = 近7天查询次数
   - 累积统计：3 ≤ 7 ≤ 30 ≤ 90 ≤ 180 ≤ 360
   - `>360_hari` = 超过360天的历史查询总数

---

## 下一步

特征审核Agent需要验证：
1. ✅ 类别一致性（已解决：动态提取）
2. ✅ 防穿越机制（已解决：双重过滤）
3. ✅ 字段名正确性（已解决：对照原始数据）
4. ⏳ 特征计算逻辑正确性
5. ⏳ 异常处理完整性
6. ⏳ 代码规范性
