# 特征评估Agent总结

**日期**: 2026-05-04
**状态**: ✅ 已完成

## 核心功能

特征评估Agent负责筛选高质量特征，通过三个关键指标：

1. **IV (Information Value)**: 衡量特征的预测能力，>= 0.02 通过
2. **PSI (Population Stability Index)**: 衡量特征的稳定性，<= 0.25 通过
3. **覆盖率**: 衡量特征的非缺失比例，> 5% 通过

## 技术实现

### 文件结构

```
agents/feature_evaluation_agent.py
├── FeatureEvaluator类
│   ├── load_feature_calculator()  - 动态导入特征代码
│   ├── load_sample_data()         - 加载JSON/JSONL/Excel样本
│   ├── split_data()               - 划分训练集/OOT
│   ├── calculate_iv()             - 计算IV值
│   ├── calculate_psi()            - 计算PSI
│   ├── calculate_coverage()       - 计算覆盖率
│   ├── evaluate_all_features()    - 批量评估
│   ├── generate_html_report()     - 生成HTML报告
│   └── run()                      - 主流程
```

### 关键算法

#### IV计算
```python
# 分箱处理（连续特征分10箱）
bin_table = df.groupby(pd.qcut(values, q=10))[target].agg(['sum', 'count'])

# IV公式
iv = Σ (bad_pct - good_pct) * ln(bad_pct / good_pct)
```

#### PSI计算
```python
# 使用训练集的分位数进行分箱
bins = pd.qcut(train_values, q=10, retbins=True)[1]

# 应用相同分箱到两个数据集
train_dist = pd.cut(train_values, bins).value_counts(normalize=True)
oot_dist = pd.cut(oot_values, bins).value_counts(normalize=True)

# PSI公式
psi = Σ (oot_pct - train_pct) * ln(oot_pct / train_pct)
```

### 输出

| 文件 | 内容 |
|------|------|
| `outputs/evaluation/feature_evaluation_report.html` | HTML评估报告 |
| `outputs/evaluation/passed_features.json` | 通过筛选的特征列表 |

## 使用方式

### 独立运行
```bash
python agents/feature_evaluation_agent.py
```

### 通过主Agent运行
```bash
python agents/feature_orchestrator.py --start-from feature_evaluation
```

## HTML报告示例

报告包含：
- **概要**: 总特征数、通过数、通过率
- **筛选阈值**: IV/PSI/覆盖率阈值
- **详细结果表格**: 按IV降序排列的所有特征

```html
特征名称                    IV      PSI     覆盖率    状态
cross_age_gambling        0.0523  0.1234  95.2%    ✅ 通过
ratio_loan_apps           0.0312  0.0876  88.5%    ✅ 通过
...
```

## 筛选流程

```
审核通过的代码
    ↓
加载 FeatureCalculator
    ↓
划分训练集/OOT (80/20)
    ↓
计算所有特征
    ↓
┌─────────────────────────┐
│ 对每个特征:              │
│ ├─ 计算 IV >= 0.02      │
│ ├─ 计算 PSI <= 0.25     │
│ └─ 计算覆盖率 > 5%      │
└─────────────────────────┘
    ↓
筛选通过的特征
    ↓
生成HTML报告 + JSON
```

## 相关文件

- `agents/feature_evaluation_agent.py` - 核心实现
- `agents/feature_orchestrator.py` - 主Agent集成
- `outputs/evaluation/feature_evaluation_report.html` - HTML报告
- `outputs/evaluation/passed_features.json` - 通过特征列表

## 后续扩展

当前实现是基础版本，未来可以扩展：
- [ ] 支持多分类IV计算
- [ ] 支持时序交叉验证
- [ ] 特征相关性分析
- [ ] 自动化特征选择建议
- [ ] Plotly交互式可视化
