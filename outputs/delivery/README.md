# 风控特征交付包 v23

**生成时间**: 2026-05-31  
**总评估特征**: 267  
**通过特征**: 155 (58.1%，IV >= 0.02, PSI <= 0.25, 覆盖率 > 5%)  
**部署版本**: v23

---

## 目录结构

```
outputs/deployment/v23/
├── core/
│   ├── feature_calculator.py    # 特征计算核心代码（267个特征）
│   └── category_config.json      # APP分类缓存（用于赌博/现金贷等分类）
├── config/
│   ├── version.json              # 版本信息 + 每个通过的配置
│   └── config.yaml               # 部署配置
├── api/
│   └── app.py                    # FastAPI 服务（供线上接口调用）
├── examples/
│   └── api_usage.py              # API调用示例代码
├── tests/                        # 测试目录（空）
├── docs/                         # 文档目录
├── requirements.txt              # Python依赖
└── deploy/                       # 部署脚本

outputs/delivery/
├── README.md                     # 本文档
├── delivery_note_v23.txt         # 交付说明（含Top 20和模板统计）
├── passed_features_v23.csv       # 155个通过特征名单（含IV/PSI/覆盖率）
└── all_features_v23.csv          # 全部267个特征（含未通过原因）
```

---

## 一、输入数据格式说明

每个样本是一个**订单JSON对象**，与短链调回来的数据结构完全一致。
特征计算器只需要解析 `params` 内的三个字段，其他字段（如 `country`、`Indo_XD_score`）无关。

```json
{
  "orderId": "id002luzt202603090951432723072",
  "applyTime": 1700000000000,
  "params": {
    "base": {
      "salary": 12000000,
      "workYears": 4,
      "marita": 1,
      "gender": 0,
      "job": "12",
      "birthday": "15-02-1973",
      "children": 0,
      "appname": "flex-rupiah"
    },
    "appList": [
      {
        "packageX": "com.game.gambling",
        "sysApp": 0,
        "upTime": 1700000000
      },
      {
        "packageX": "com.social.tiktok",
        "sysApp": 0,
        "upTime": 1690000000
      }
    ],
    "FDC": {
      "pinjaman": [
        {
          "nilai_pendanaan": 8000000,
          "tipe_pinjaman": "Multiguna",
          "status_pinjaman": "lunas",
          "kualitas_pinjaman": "1",
          "id_penyelenggara": "lender_a",
          "pendanaan_syariah": "false",
          "tgl_penyaluran_dana": "2026-01-15"
        }
      ],
      "history_inquiry": {
        "statistic": {
          "3_hari": 2,
          "7_hari": 3,
          "15_hari": 4,
          "30_hari": 5,
          "60_hari": 8,
          "90_hari": 10,
          "180_hari": 15
        }
      }
    }
  }
}
```

**交付方式**：直接把 `data/all_samples/` 里的JSON文件给IT团队就行，他们线上也是同样的数据结构。每个订单一个JSON文件，或者一个JSON数组（多个订单）。

## 二、IT团队：集成到线上评分服务

### 方式1：直接Python调用（推荐）

```python
# 把 outputs/deployment/v23/core/ 整个目录复制到线上服务
from feature_calculator import FeatureCalculator

# 初始化（加载一次，所有订单复用）
calculator = FeatureCalculator()

# 对每个订单计算特征
def score_order(order_data: dict) -> dict:
    """
    Args:
        order_data: 订单JSON（与上面格式一致）
    Returns:
        {"cnt_fdciq_3d": 2.0, "cnt_fdcpin_30d": 5.0, ..., "dev_salary_peer": 0.8}
    """
    features = calculator.calculate_all(order_data)
    return features
```

**重要**: `feature_calculator.py` 依赖同目录下的 `channel1_calculators.py`（所有计算函数定义），部署时必须一起复制。

### 方式2：启动API服务

```bash
cd outputs/deployment/v23
pip install -r requirements.txt
python api/app.py
# 服务启动在 http://localhost:8000

# 单样本计算
curl -X POST http://localhost:8000/api/v1/calculate \
  -H "Content-Type: application/json" \
  -d '{"order_id": "...", "raw_data": {...}}'

# 批量计算
curl -X POST http://localhost:8000/api/v1/calculate_batch \
  -H "Content-Type: application/json" \
  -d '{"samples": [...], "batch_size": 5}'
```

---

## 三、风控团队：用新样本验证

风控团队拿到新样本数据后，数据格式和上面一样。只需要把新样本JSON传给 `FeatureCalculator` 就能算出所有特征值。

### 验证脚本（新样本验证特征）

部署包自带 `examples/api_usage.py`。如果要批量验证新样本，用JSON数组格式存放新样本：

```python
"""
新样本验证脚本 — 用新数据验证155个通过特征的稳定性
"""
import json
import sys
import os

# 添加core路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'core'))
from feature_calculator import FeatureCalculator


def validate_on_new_samples(new_samples_path: str, output_path: str = "validation_result.json"):
    """
    用新样本数据跑特征，输出每个特征的值分布
    
    Args:
        new_samples_path: 新样本JSON文件路径
            格式: [{"orderId": "...", "params": {...}}, ...]
            与训练数据格式完全一致
    """
    with open(new_samples_path) as f:
        samples = json.load(f)
    
    calculator = FeatureCalculator()
    
    results = []
    for sample in samples:
        features = calculator.calculate_all(sample)
        results.append({
            "order_id": sample.get("orderId"),
            "features": features
        })
    
    # 输出为JSON
    with open(output_path, 'w') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    # 打印统计摘要
    from collections import Counter
    feature_values = {}
    for r in results:
        for name, val in r["features"].items():
            if name not in feature_values:
                feature_values[name] = []
            feature_values[name].append(val)
    
    print(f"验证样本数: {len(samples)}")
    print(f"特征数: {len(feature_values)}")
    print()
    print("Top 10 特征均值:")
    for name in list(feature_values.keys())[:10]:
        vals = [v for v in feature_values[name] if v is not None]
        if vals:
            print(f"  {name:<40s} mean={sum(vals)/len(vals):.4f} 非空={len(vals)}")
    
    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("new_samples", help="新样本JSON文件路径")
    parser.add_argument("--output", default="validation_result.json", help="输出路径")
    args = parser.parse_args()
    
    validate_on_new_samples(args.new_samples, args.output)
```

### 使用方法

```bash
cd outputs/deployment/v23

# 运行验证
python validate_features.py /path/to/new_samples.json --output validation_result.json

# 然后将结果与 outputs/evaluation/feature_evaluation_report.html 对比
# 检查:
# 1. 特征值分布是否合理（无异常极值）
# 2. 缺失率是否稳定
# 3. PSI是否 <= 0.25（分布偏移检测）
```

### API用法（线上服务）

```python
# 1. 启动API服务
# cd outputs/deployment/v23 && python api/app.py

# 2. 调用特征计算（每个订单调一次）
curl -X POST http://localhost:8000/api/v1/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": "id002luzt202603090951432723072",
    "raw_data": {
      "params": {
        "base": {"salary": 12000000},
        "appList": [{"packageX": "com.game.gambling", "sysApp": 0, "upTime": 1700000000}],
        "FDC": {
          "pinjaman": [{"nilai_pendanaan": 8000000, "tipe_pinjaman": "Multiguna"}],
          "history_inquiry": {"statistic": {"30_hari": 5}}
        }
      }
    }
  }'

# 3. 返回示例
# {"features": {"cnt_fdciq_30d": 5, "cnt_fdcpin_30d": 1, ..., "dev_salary_peer": 0.8}}
```

---

## 三、特征清单说明

| 模板类型 | 通过数 | 说明 |
|---------|-------|------|
| 计数(T001) | 47 | PINJAMAN/INQUIRY/APP在不同窗口的计数 |
| 去重计数(T002) | 12 | PINJAMAN去重机构/类型/状态 |
| 衰减求和(T003) | 16 | 贷款金额衰减加权求和 |
| 占比(T004) | 28 | 赌博/现金贷APP占比、贷款类型占比 |
| 集中度(T005) | 20 | 贷款机构集中度(Gini/Entropy/CV) |
| 周期对比(T007) | 7 | 不同窗口的增速对比 |
| 趋势(T008) | 6 | 查询/贷款的趋势斜率 |
| 突增(T009) | 5 | APP安装/贷款突增检测 |
| 百分位(T010) | 4 | 用户在全量中的百分位定位 |
| 偏差(T011) | 4 | 用户与群体均值的偏差 |
| 异常检测(T012) | 1 | 贷款模式异常检测 |
| 申报vs实际(T013) | 3 | 申报收入与实际贷款的比值/差值 |
| 交叉差异(T014) | 1 | 跨源信息不一致检测 |
| 一致性(T015) | 1 | 设备和贷款机构集群一致性 |

### Top 5 强特征（重点推荐）

| 特征名 | IV | 业务含义 |
|--------|-----|---------|
| da_salary_loan_ratio | 0.531 | 收入 vs 贷款金额比（越低风险越高） |
| pctl_salary_pop | 0.522 | 收入在全量用户中的百分位 |
| dev_salary_peer | 0.522 | 收入与群体均值的偏差 |
| da_salary_loan_gap | 0.519 | 收入与贷款金额的差额 |
| uniq_fdcpin_loan_status_30d | 0.279 | 近30天不同贷款状态数 |

---

## 四、常见问题

**Q: 新样本的数据格式和训练时不一样怎么办？**  
A: 特征计算器要求数据结构包含 `params.base`（基础信息）、`params.appList`（APP列表）、`params.FDC`（信用报告）。如果线上数据字段名不同，需要做一层字段映射。

**Q: 需要加载APP分类缓存吗？**  
A: gambling/cash_loan 等分类特征需要。默认自动加载 `core/category_config.json`。如果没有该文件，相关分类特征返回0。

**Q: 157KB的部署包能不能减小？**  
A: 可以用 `--mode mass-produce` 重新生成时只保留通过特征（当前是全部267个）。或者手动删除 `feature_calculator.py` 中未通过的特征函数调用和对应的 return 条目。
