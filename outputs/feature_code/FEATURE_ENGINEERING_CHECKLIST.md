# 特征工程开发检查清单（必读）

本文档是特征工程开发的完整检查清单，确保不遗漏任何关键点。

---

## 一、开发前准备

### 1.1 理解原始数据结构

- [ ] 已查看短链JSON的完整结构
- [ ] 已确认`applyTime`字段（毫秒时间戳）
- [ ] 已确认`params.base`的所有字段
- [ ] 已确认`params.appList`的结构（inTime, upTime, packageX等）
- [ ] 已确认`params.FDC`的结构
  - [ ] history_inquiry.statistic
  - [ ] pinjaman[] 贷款记录
  - [ ] platform_aktif.jumlahPlatformAktif

### 1.2 理解特征设计文档

- [ ] 已读取`outputs/feature_design/feature_design_doc.json`
- [ ] 理解每个特征的`calculation_logic`字段
- [ ] 按数据源分类特征（applist/fdc/base）
- [ ] 确认特征总数

---

## 二、代码开发

### 2.1 应用分类（动态提取）

- [ ] 从`app_classification_cache`加载11,850个应用分类
- [ ] 动态提取所有类别到`self.standard_categories`
- [ ] **禁止硬编码类别名称**

```python
# ✅ 正确
def _extract_standard_categories(self) -> set:
    categories = set()
    for pkg_info in self.app_classification_cache.values():
        category = pkg_info.get('category', 'other')
        if category:
            categories.add(category)
    return categories

# ❌ 错误
STANDARD_CATEGORIES = {'gambling', 'cash_loan', ...}
```

---

### 2.2 防穿越机制

#### applist过滤

- [ ] 同时检查`inTime AND upTime <= applyTime`
- [ ] applyTime从`data['applyTime']`获取（毫秒时间戳）

```python
# ✅ 正确
apply_time_ms = apply_time_dt.timestamp() * 1000
filtered = [
    app for app in app_list
    if app.get('inTime', 0) <= apply_time_ms and app.get('upTime', 0) <= apply_time_ms
]
```

#### FDC过滤

- [ ] 检查`tgl_penyaluran_dana <= apply_time.date()`
- [ ] 遍历`pinjaman[]`列表

```python
# ✅ 正确
apply_date = apply_time_dt.date()
for loan in fdc['pinjaman']:
    disburse_str = loan.get('tgl_penyaluran_dana', '')
    if disburse_str:
        disburse_date = datetime.strptime(disburse_str, '%Y-%m-%d').date()
        if disburse_date <= apply_date:
            filtered_pinjaman.append(loan)
```

#### 时间窗口计算

- [ ] 从`apply_time`往前推（timedelta）
- [ ] **禁止使用当前系统时间**

```python
# ✅ 正确
cutoff_30d = apply_time_dt.date() - timedelta(days=30)
loans_30d = [l for l in pinjaman if l_date >= cutoff_30d]

# ❌ 错误
now = datetime.now()  # 禁止！
```

---

### 2.3 特征计算

#### 从原始数据开始

- [ ] applist：遍历`filtered_applist`并分类
- [ ] 统计各类别数量
- [ ] 基于分类结果计算特征

```python
# ✅ 正确
app_categories = {}
for app in filtered_applist:
    pkg = app.get('packageX', '')
    if pkg in self.app_classification_cache:
        app_categories[pkg] = self.app_classification_cache[pkg].get('category', 'other')

cat_counts = {}
for cat in app_categories.values():
    cat_counts[cat] = cat_counts.get(cat, 0) + 1

# 计算特征
total_apps = len(filtered_applist)
high_risk_count = sum(cat_counts.get(c, 0) for c in ['gambling', 'cash_loan', ...])
features['ratio_applist_highrisk_apps_all'] = high_risk_count / total_apps
```

#### FDC特征

- [ ] 使用`history_inquiry.statistic['3_hari']`等
- [ ] 使用`platform_aktif.jumlahPlatformAktif`
- [ ] 遍历`pinjaman[]`进行统计

```python
# ✅ 正确
fdc_stat = fdc.get('history_inquiry', {}).get('statistic', {})
q3d = fdc_stat.get('3_hari', 0)
q7d = fdc_stat.get('7_hari', 0)

active_plat = fdc.get('platform_aktif', {}).get('jumlahPlatformAktif', 0)

dpd_90plus = sum(1 for l in pinjaman if l.get('dpd_max', 0) > 90)
```

#### Base特征

- [ ] 从`data['params']['base']`读取
- [ ] 正确解析年龄（从birthday）
- [ ] 处理职业代码（job字段）

```python
# ✅ 正确
base = data.get('params', {}).get('base', {})
birthday_str = base.get('birthday', '')
if birthday_str:
    bday = datetime.strptime(birthday_str, '%d-%m-%Y')
    age = (apply_time_dt - bday).days // 365
```

---

### 2.4 异常处理

- [ ] 安全除法（除0返回0）
- [ ] 日期格式错误处理
- [ ] 缺失字段处理
- [ ] 空列表/字典处理

```python
# ✅ 正确
@staticmethod
def _safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    return numerator / denominator if denominator != 0 else default

# 使用
features['ratio_xxx'] = self._safe_div(count, total)
```

---

## 三、代码质量

### 3.1 注释规范

- [ ] 所有业务逻辑使用中文注释
- [ ] 防穿越机制说明
- [ ] 特征计算逻辑说明

```python
# 1. ratio_applist_highrisk_apps_all
# 高风险应用占比
high_risk_cats = ['gambling', 'cash_loan', 'fintech_lending', 'fake_gps', 'clone_app']
high_risk_count = sum(cat_counts.get(c, 0) for c in high_risk_cats)
features['ratio_applist_highrisk_apps_all'] = self._safe_div(high_risk_count, total_apps)
```

### 3.2 函数独立性

- [ ] 每个模块特征有独立函数
- [ ] `_calc_applist_features()`
- [ ] `_calc_fdc_features()`
- [ ] `_calc_base_features()`

### 3.3 返回值统一

- [ ] 所有特征计算函数返回`Dict[str, float]`
- [ ] 特征名称与设计文档一致

---

## 四、验证测试

### 4.1 代码语法

- [ ] 无语法错误
- [ ] 所有import正确
- [ ] 类和方法签名正确

### 4.2 数据一致性

- [ ] 类别数量 = 17（动态提取）
- [ ] 应用分类cache加载成功（11,850个）
- [ ] 所有字段名已对照原始JSON验证

### 4.3 防穿越测试

- [ ] applist过滤后数量 ≤ 原始数量
- [ ] FDC过滤后贷款数 ≤ 原始数量
- [ ] 所有特征只使用applyTime之前的数据

---

## 五、不可违背的原则

### 原则1：动态适配特征设计

> 特征工程Agent是**代码生成器**，根据特征设计文档动态生成代码。

- ❌ 不硬编码特征计算逻辑
- ✅ 读取`calculation_logic`字段
- ✅ 生成对应的Python代码

### 原则2：分类来源于分类结果

> 所有类别都从`app_classification_cache`动态提取。

- ❌ 不硬编码类别名称
- ✅ 从分类JSON提取
- ✅ 单一数据源

### 原则3：防穿越是核心

> 所有特征计算只能使用**申请时间之前**的数据。

- ✅ applyTime是唯一基准点
- ✅ applist同时过滤inTime和upTime
- ✅ FDC过滤放款日期

### 原则4：对照原始数据结构

> 所有字段名必须先对照原始JSON确认。

- ❌ 不假设字段名
- ✅ 实际查看JSON
- ✅ 理解印尼语字段

### 原则5：从原始数据计算

> 所有特征都从原始JSON开始计算。

- ❌ 不假设预计算字段
- ✅ 遍历appList、pinjaman
- ✅ 实时统计和计算

---

## 六、常见错误（避免踩坑）

### 错误1：硬编码类别

```python
# ❌ 错误
STANDARD_CATEGORIES = {'gambling', 'cash_loan', ...}

# ✅ 正确
self.standard_categories = self._extract_standard_categories()
```

### 错误2：只过滤inTime

```python
# ❌ 错误
filtered = [app for app in app_list if app.get('inTime', 0) <= apply_time_ms]

# ✅ 正确
filtered = [
    app for app in app_list
    if app.get('inTime', 0) <= apply_time_ms and app.get('upTime', 0) <= apply_time_ms
]
```

### 错误3：错误的FDC字段

```python
# ❌ 错误
q3d = inquiry.get('last_3days', 0)

# ✅ 正确
fdc_stat = fdc.get('history_inquiry', {}).get('statistic', {})
q3d = fdc_stat.get('3_hari', 0)
```

### 错误4：假设预计算字段

```python
# ❌ 错误
gambling = data.get('gambling_count', 0)

# ✅ 正确
cat_counts = {}
for app in filtered_applist:
    pkg = app.get('packageX', '')
    cat = self.app_classification_cache.get(pkg, {}).get('category', 'other')
    cat_counts[cat] = cat_counts.get(cat, 0) + 1
gambling = cat_counts.get('gambling', 0)
```

---

## 七、参考文档

- **LESSONS_LEARNED.md** - 项目踩坑经验总结
- **FEATURE_ENGINEERING_KEY_LESSONS.md** - 特征工程详细经验
- **FEATURE_CALCULATOR_V2_IMPROVEMENTS.md** - 代码改进总结
- **FEATURE_REVIEW_IMPROVEMENTS.md** - 审核Agent改进总结（2026-05-04）
- **特征设计文档** - `outputs/feature_design/feature_design_doc.json`
- **分类结果** - `outputs/app_analysis/classification_complete_11850.json`
- **类别配置** - `outputs/feature_code/feature_categories_config.json`

---

## 八、流程编排

### 主Agent协调

特征工程流程由 `FeatureOrchestrator` 统一协调：

```bash
# 执行完整流程
python agents/feature_orchestrator.py

# 从特定步骤开始（断点续做）
python agents/feature_orchestrator.py --start-from feature_review

# 查看状态
python agents/feature_orchestrator.py --status
```

### Human-in-the-Loop

特征审核步骤包含人工确认环节：
1. 自动执行语法和逻辑检查
2. LLM深度审核
3. **暂停等待人工确认**
4. 用户输入 `yes`/`no` 决定最终结果

### 类别配置动态化

业务规则类别不再hardcoded，改为外部配置：
- 配置文件: `feature_categories_config.json`
- 包含: high_risk, loan, financial等类别列表
- 优势: 修改类别无需改代码，支持热更新

---

**最后更新**: 2026-05-04（FeatureOrchestrator创建）
**适用场景**: 所有特征工程开发任务
