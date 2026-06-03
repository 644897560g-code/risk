# 特征评估Agent使用说明

**日期**: 2026-05-04

## 真实数据配置

### 数据文件

| 文件 | 路径 | 说明 |
|------|------|------|
| 短链URL | `0421全样本短链.txt` | 2915条订单的短链URL |
| 标签Excel | `印尼模型分_2026_04_21_建模样本aiagent.xlsx` | 2272条订单的好坏标签 |

### 数据流程

```
短链URL文件
    ↓
从URL获取JSON数据 (requests)
    ↓
合并Excel标签 (pandas)
    ↓
完整样本数据 (带is_overdue标签)
    ↓
划分训练集/OOT
    ↓
特征计算 + 评估
```

## 使用方式

### 命令行运行

```bash
# 使用真实数据（全部样本）
python agents/feature_evaluation_agent.py \
    --short-urls 0421全样本短链.txt \
    --labels 印尼模型分_2026_04_21_建模样本aiagent.xlsx

# 采样测试（前100条）
python agents/feature_evaluation_agent.py \
    --short-urls 0421全样本短链.txt \
    --labels 印尼模型分_2026_04_21_建模样本aiagent.xlsx \
    --sample-size 100

# 自定义OOT比例
python agents/feature_evaluation_agent.py \
    --short-urls 0421全样本短链.txt \
    --labels 印尼模型分_2026_04_21_建模样本aiagent.xlsx \
    --oot-ratio 0.3
```

### 通过主Agent运行

```bash
python agents/feature_orchestrator.py --start-from feature_evaluation
```

## 代码修改总结

### 主要变更

| 修改项 | 原实现 | 新实现 |
|--------|--------|--------|
| 数据加载 | 本地JSON/JSONL | URL请求 + Excel标签合并 |
| 样本格式 | 单条JSON | 带is_overdue标签的完整数据 |
| 命令行参数 | 无 | --short-urls, --labels, --sample-size |

### 新增方法

- `load_short_urls()`: 加载短链URL文件
- `fetch_json_from_url()`: 从URL获取JSON数据
- `load_labels_from_excel()`: 从Excel加载标签
- `load_sample_data()`: 新的数据加载方法（URL+标签）
- `load_sample_data_legacy()`: 旧版方法（兼容用）

### 数据结构示意图

```python
# 合并后的样本结构
{
    "orderId": "id002luzt202603090951432723072",
    "country": "INDO",
    "params": {
        "base": {...},
        "appList": [...],
        "FDC": {...}
    },
    "is_overdue": 1,  # <-- 从Excel合并的标签
    ...
}
```

## 注意事项

1. **网络请求**: 从短链获取JSON需要网络连接
2. **标签匹配**: 通过`orderId`与Excel中的`source_order_no`匹配
3. **缺失标签**: 未匹配的样本`is_overdue`设为-1
4. **采样测试**: 建议先用`--sample-size 100`测试

## 输出文件

| 文件 | 说明 |
|------|------|
| `outputs/evaluation/feature_evaluation_report.html` | HTML评估报告 |
| `outputs/evaluation/passed_features.json` | 通过筛选的特征列表 |

## 集成主Agent

主Agent中的调用方式：

```python
def _run_feature_evaluation(self) -> bool:
    code_file = self.data_flow.get_latest_output('features_calculator')

    self.evaluation_agent.run(
        code_path=code_file,
        short_url_file='0421全样本短链.txt',
        labels_excel='印尼模型分_2026_04_21_建模样本aiagent.xlsx',
        sample_size=None,  # 全部样本
        oot_ratio=0.2
    )
```
