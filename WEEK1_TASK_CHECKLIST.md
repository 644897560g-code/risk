# Week 1 执行清单：特征设计Agent升级

**目标**: 设计500个特征的生成方案
**时间**: 7天

---

## Day 1-2: 特征模板设计

### 任务清单
- [ ] 分析现有特征类型
- [ ] 设计20+特征模板
- [ ] 定义模板语法
- [ ] 创建模板配置文件

### 交付物
`outputs/feature_templates/`:
```
- ratio_template.yaml      # 比例类模板
- count_template.yaml       # 统计类模板
- cross_template.yaml       # 交叉类模板
- trend_template.yaml       # 趋势类模板
- fdc_template.yaml         # FDC模板
- ...
```

### 示例模板
```yaml
template_id: ratio_fdc_loan_count_period
template_name: "FDC借贷次数占比_{period}天"
category: fdc_feature
parameters:
  period: [3, 7, 30, 90]
  metric: [count, sum]
formula: |
  len(pinjaman where date >= now - {period} days) / len(pinjaman)
description: "近{period}天内的借贷申请次数占总借贷次数的比例"
business_value: "反映用户近期借贷活跃度"
```

---

## Day 3-4: FDC深度挖掘

### 任务清单
- [ ] 解析FDC数据结构
- [ ] 分析pinjaman记录（贷款历史）
- [ ] 分析history_inquiry（查询历史）
- [ ] 分析platform_aktif（活跃平台）
- [ ] 设计衍生特征

### FDC数据结构分析

**pinjaman（贷款记录）**:
- 贷款金额
- 贷款日期
- 还款日期
- 平台名称
- 是否逾期
- 逾期天数

**可生成特征**:
```
- count_pinjaman_total: 总贷款笔数
- count_pinjaman_active: 活跃平台数
- count_pinjaman_overdue: 逾期笔数
- ratio_pinjaman_overdue: 逾期比例
- amt_pinjaman_avg: 平均贷款金额
- days_since_last_loan: 距上次贷款天数
- trend_pinjaman_count_30d: 近30天贷款趋势
- ...
```

**history_inquiry（查询历史）**:
- 查询日期
- 查询机构
- 查询类型

**可生成特征**:
```
- count_inquiry_total: 总查询次数
- count_inquiry_3d: 近3天查询
- count_inquiry_7d: 近7天查询
- count_inquiry_30d: 近30天查询
- ratio_inquiry_fintech: 金融科技公司查询占比
- trend_inquiry_count_7d: 近7天查询趋势
- ...
```

### 交付物
`outputs/fdc_analysis/fdc_feature_design.json`:
```json
{
  "pinjaman_features": [
    {"name": "count_pinjaman_total", "type": "count", "source": "pinjaman"},
    {"name": "count_pinjaman_overdue", "type": "count", "source": "pinjaman"},
    ...
  ],
  "inquiry_features": [...],
  "platform_features": [...]
}
```

---

## Day 5: 交叉特征设计

### 任务清单
- [ ] 设计base × applist交叉特征
- [ ] 设计base × FDC交叉特征
- [ ] 设计applist × FDC交叉特征
- [ ] 生成50+交叉特征方案

### 交叉特征示例

**base × applist**:
```
- cross_base_age_gambling_apps: 年龄×赌博APP数
- cross_base_salary_loan_apps: 薪资×借贷APP数
- cross_base_gender_risk_apps: 性别×风险APP占比
- cross_base_martial_fintech: 婚姻×金融科技APP
```

**base × FDC**:
```
- cross_base_age_loan_count: 年龄×贷款次数
- cross_base_gender_overdue: 性别×逾期比例
- cross_base_region_inquiry: 地区×查询次数
```

**applist × FDC**:
```
- cross_applist_gambling_loan: 赌博APP×贷款次数
- cross_applist_risk_overdue: 风险APP×逾期
- cross_applist_category_inquiry: APP类别×查询
```

---

## Day 6: 时序特征设计

### 任务清单
- [ ] 设计时序特征模板
- [ ] 设计多时间窗口
- [ ] 生成50+时序特征方案

### 时序特征

**安装趋势**:
```
- trend_applist_install_1d: 近1天安装数
- trend_applist_install_3d: 近3天安装数
- trend_applist_install_7d: 近7天安装数
- trend_applist_install_trend: 安装趋势（斜率）
```

**查询趋势**:
```
- trend_inquiry_3d_vs_7d: 近3天vs近7天查询比
- trend_inquiry_7d_vs_30d: 近7天vs近30天查询比
- trend_inquiry_slope: 查询斜率
```

**借贷趋势**:
```
- trend_loan_3d_vs_7d
- trend_loan_7d_vs_30d
- trend_loan_slope
```

---

## Day 7: 生成500个特征方案

### 任务清单
- [ ] 编写特征生成脚本
- [ ] 执行生成500个方案
- [ ] 验证方案合理性
- [ ] 保存到JSON文件

### 生成脚本
```python
# generate_feature_designs.py
import json
import yaml
from itertools import product

# 加载所有模板
templates = load_all_templates()

# 生成所有参数组合
feature_designs = []
for template in templates:
    params = template['parameters']
    for param_values in product(*params.values()):
        design = fill_template(template, zip(params.keys(), param_values))
        feature_designs.append(design)

# 保存
with open('outputs/feature_design/designs_500.json', 'w') as f:
    json.dump(feature_designs, f, ensure_ascii=False, indent=2)

print(f"生成{len(feature_designs)}个特征设计方案")
```

### 交付物
`outputs/feature_design/designs_500.json`:
```json
[
  {
    "feature_name": "ratio_fdc_loan_count_3d",
    "category": "fdc_feature",
    "formula": "...",
    "description": "...",
    "business_value": "..."
  },
  ...
]
```

---

## Week 1 验收标准

- [ ] 设计文档完整（模板、FDC分析、交叉、时序）
- [ ] 生成500+特征设计方案
- [ ] 方案质量检查（无重复、业务合理）
- [ ] JSON文件保存

---

**预计完成时间**: 2026-05-11

是否开始执行？
