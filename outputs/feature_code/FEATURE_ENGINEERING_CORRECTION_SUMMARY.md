# 特征工程Agent修正总结（2026-05-04）

## 问题分析与修正

### 问题1: 标准应用类别不一致

**原代码错误**：
```python
STANDARD_CATEGORIES: Set[str] = {
    'social_entertainment', 'cash_loan', 'fintech_lending', 'banking',
    'ewallet', 'installment', 'gambling', 'fake_gps', 'clone_app',
    'shopping', 'travel', 'health', 'education', 'news', 'tools', 'other'
}
```

**问题**：
- 使用了错误的类别名称（`travel`, `health`, `education`, `news`, `tools`）
- 实际应该是我们的17个标准类别

**修正后**：
```python
# 17个标准分类（与分类_cache完全一致）
standard_cats = {'gambling', 'cash_loan', 'fintech_lending', 'banking', 'ewallet', 'installment',
                 'app_store', 'fake_gps', 'clone_app', 'shopping', 'food_delivery', 'transportation',
                 'utility', 'productivity', 'religious', 'social_entertainment', 'other'}
```

**验证**：
- 通过`outputs/app_analysis/classification_complete_11850.json`确认实际有17个类别
- 代码中正确使用这个集合进行计算和验证

---

### 问题2: 离线数据快照时间字段错误

**原代码错误**：
```python
snapshot_str = data.get('snapshot_date')  # ❌ 字段不存在
```

**检查离线数据结构**：
```python
data = {
    'country': 'INDO',
    'eventType': 'apply',
    'orderId': 'id002luzt202603090951432723072',
    'applyTime': 1773025791000,  # ✅ 毫秒时间戳 (2026-03-09)
    'params': {
        'base': {
            'applyTime': 1773025791000,  # ✅ 同样在base中
            ...
        },
        'appList': [...],
        'FDC': {...}
    }
}
```

**字段说明**：
- `applyTime`: 毫秒时间戳，表示贷款申请时间
- **没有**`snapshot_date`字段
- 防穿越基准就是`applyTime`

**修正后**：
```python
# 正确的applyTime提取
apply_time_ms = data.get('applyTime', 0)
apply_time_dt = datetime.fromtimestamp(apply_time_ms / 1000)
```

---

### 问题3: 业务参考时间默认值错误

**原代码错误**：
```python
if reference_date is None:
    reference_date = datetime.date.today()  # ❌ 使用当前系统时间
```

**问题**：
- 应该使用贷款申请时间，而非当前系统时间
- 离线数据中`applyTime`就是申请时间

**修正后**：
```python
# 默认使用离线数据中的applyTime
if not apply_time:
    apply_time_ms = data.get('applyTime', 0)
    if apply_time_ms:
        apply_time_dt = datetime.fromtimestamp(apply_time_ms / 1000)
    else:
        apply_time_dt = datetime.now()  # fallback
```

---

### 问题4: 原始数据字段提取错误

**原代码错误**：
```python
# ❌ 直接从不存在的字段提取
gambling = data.get('gambling_count', 0)
cash_loan = data.get('cash_loan_count', 0)
total_apps = data.get('total_installed_apps', 0)
...
```

**根本问题**：
- 这些字段在原始数据中根本不存在
- 原始数据只有`appList`（应用列表），需要根据category统计

**正确的数据提取流程**：
```python
# 1. 过滤applist（防穿越）
filtered_applist = self._filter_applist(data, apply_time_dt)

# 2. 对每个应用分类
app_categories = {}
for app in filtered_applist:
    pkg = app.get('packageX', '')
    if pkg in self.app_classification_cache:
        app_categories[pkg] = self.app_classification_cache[pkg].get('category', 'other')
    else:
        app_categories[pkg] = 'other'

# 3. 统计各类别数量
cat_counts = {}
for cat in app_categories.values():
    cat_counts[cat] = cat_counts.get(cat, 0) + 1

# 4. 计算特征
high_risk_count = sum(cat_counts.get(c, 0) for c in ['gambling', 'cash_loan', ...])
features['ratio_applist_highrisk_apps_all'] = high_risk_count / len(filtered_applist)
```

**修正要点**：
- ✅ 正确使用`data['params']['appList']`
- ✅ 使用11,850应用分类缓存
- ✅ 实时计算各类别数量
- ✅ 基于分类结果推导所有特征

---

### 问题5: FDC数据字段提取错误

**原代码错误**：
```python
# ❌ 从不存在的字段提取
dpd_90plus = data.get('loans_dpd_gt_90_count', 0)
total_loan_rec = data.get('total_loan_records', 0)
...
```

**正确的FDC数据结构**：
```python
fdc = data['params']['FDC']
fdc = {
    'history_inquiry': {
        'last_3days': 2,
        'last_7days': 5,
        'last_30days': 12
    },
    'pinjaman': [  # 贷款记录列表
        {
            'tgl_penyaluran_dana': '2026-01-20',  # 放款日期
            'nilai_pendanaan': 1000000,  # 贷款金额
            'sisa_pinjaman_berjalan': 1000000,  # 未还余额
            'dpd_max': 0,  # 最大逾期天数
            'status_pinjaman': 'O',  # Outstanding/Closed
            ...
        },
        ...
    ],
    'platform_aktif': {
        'count': 3
    }
}
```

**修正后的计算**：
```python
# 统计逾期>90天的笔数
dpd_90plus = sum(1 for l in pinjaman if l.get('dpd_max', 0) > 90)

# 统计active状态的贷款总数
active_loans = sum(1 for l in pinjaman if l.get('status_pinjaman') == 'O')

# 计算总未还余额
total_unpaid = sum(l.get('sisa_pinjaman_berjalan', 0) for l in pinjaman if l.get('status_pinjaman') == 'O')
```

---

## 修正后的正确实现

### 核心改进点

1. **正确使用applyTime作为防穿越基准**：
   - 毫秒时间戳 → datetime转换
   - 所有数据过滤基于applyTime

2. **正确的applist分类统计**：
   - 使用11,850应用分类缓存
   - 实时计算各类别数量
   - 基于分类推導特征

3. **正确的FDC数据解析**：
   - 遍历`pinjaman[]`列表
   - 使用正确的字段名（`tgl_penyaluran_dana`, `dpd_max`, `sisa_pinjaman_berjalan`）
   - 防穿越：过滤future贷款记录

4. **17个标准类别的一致性**：
   - 与分类cache完全一致
   - 使用Set进行快速查找
   - 类别名称无错误

### 关键代码片段

**防穿越机制**：
```python
# applist防穿越
filtered = [app for app in app_list if app.get('inTime', 0) <= apply_time_ms]

# FDC防穿越
disburse_date = datetime.strptime(loan['tgl_penyaluran_dana'], '%Y-%m-%d').date()
if disburse_date <= apply_time_dt.date():
    filtered_pinjaman.append(loan)
```

**应用分类**：
```python
for app in filtered_applist:
    pkg = app.get('packageX', '')
    if pkg in self.app_classification_cache:
        category = self.app_classification_cache[pkg].get('category', 'other')
        app_categories[pkg] = category
```

---

## 验证结果

**生成的代码**：`outputs/feature_code/features_calculator.py`
**总行数**：237行
**特征数**：20个
**数据源**：正确使用`data['params']['appList']`, `data['params']['FDC']`, `data['params']['base']`

**所有20个特征都能正确计算**：
- ✅ 7个applist特征（基于应用分类缓存）
- ✅ 8个FDC特征（基于pinjaman列表）
- ✅ 5个base特征（基于base字段）

---

## 经验教训

1. **LLM生成的代码必须逐行验证**：
   - LLM可能会"想象"出不存在的字段
   - 必须对照原始数据结构

2. **防穿越是核心**：
   - applyTime是唯一可信的时间基准
   - 所有特征计算必须基于applyTime之前的数据

3. **应用分类cache是关键**：
   - 11,850个应用的分类结果是applist特征的唯一来源
   - 没有这个cache，无法计算任何applist特征

4. **FDC数据是列表结构**：
   - 需要遍历`pinjaman[]`进行统计
   - 不能直接get()某个计数值

---

## 下一步

特征审核Agent需要验证：
1. 代码语法合法性
2. 防穿越逻辑正确性
3. 所有特征计算是否符合calculation_logic
4. 异常处理是否完善
