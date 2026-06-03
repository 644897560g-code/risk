# 特征部署Agent使用指南

**日期**: 2026-05-04
**版本**: v1-v2

## 功能概述

特征部署Agent负责将通过评估筛选的特征代码打包成可部署的生产环境包，支持：

1. **代码裁剪**: 只保留通过筛选的特征，移除未通过的，减小部署包体积
2. **版本管理**: 基于时间戳的版本控制，支持版本回滚
3. **双模式部署**:
   - 私有化部署: 离线tar.gz压缩包（供风控团队内网部署）
   - 在线SaaS: 自动启动Docker容器（前端测试/Demo/商业化）
4. **API服务**: FastAPI实现，支持单样本和批量计算
5. **商业预留**: API密钥管理（trial/pro/enterprise）

## 目录结构

```
outputs/deployment/
├── v1/                       # 版本1目录
│   ├── core/                 # 核心计算引擎
│   │   ├── feature_calculator.py     # 裁剪后的特征代码
│   │   └── category_config.json      # 应用类别配置
│   ├── api/                  # API服务
│   │   └── app.py                    # FastAPI服务
│   ├── config/               # 配置
│   │   ├── version.json              # 版本信息
│   │   └── config.yaml               # 运行时配置
│   ├── deploy/               # Docker文件
│   │   ├── Dockerfile
│   │   └── docker-compose.yml
│   ├── docs/                 # 文档
│   │   └── README.md
│   ├── examples/             # 示例代码
│   │   ├── api_usage.py
│   │   └── test_sample.json
│   ├── tests/                # 测试
│   │   └── test_api.py
│   └── requirements.txt
├── v2/                       # 版本2目录
├── latest -> v2              # 最新版本的软链接
└── v1.tar.gz                 # 压缩部署包（供风控团队）
```

## 使用方式

### 1. 创建新部署版本

```bash
python agents/feature_deployment_agent.py
```

自动生成新版本（如v3），包含：
- 裁剪后的特征代码
- 完整的API服务
- Docker配置文件
- 版本信息

### 2. 查看所有版本

```bash
python agents/feature_deployment_agent.py --list-versions
```

输出：
```
  Version    Timestamp                 Features   Path
  ---------------------------------------------------
  v2         2026-05-04T19:35:30       2          v2
  v1         2026-05-04T19:30:55       0          v1
```

### 3. 回滚到指定版本

```bash
python agents/feature_deployment_agent.py --rollback v1
```

将`latest`软链接指向v1，回滚生效。

### 4. 手动部署

```bash
cd outputs/deployment/v2

# 方式1: Docker Compose（推荐）
docker-compose up -d

# 方式2: 直接运行
pip install -r requirements.txt
python api/app.py
```

### 5. 测试API

```bash
cd outputs/deployment/v2

# 运行测试
python tests/test_api.py

# 或直接访问
curl http://localhost:8000/
curl -X POST http://localhost:8000/api/v1/calculate \
  -H "Content-Type: application/json" \
  -d @examples/test_sample.json
```

## API接口

### 单样本计算

```bash
POST /api/v1/calculate
```

Request:
```json
{
  "order_id": "id002luzt202603090951432723072",
  "apply_time": "2026-03-09 10:00:00",
  "raw_data": {...}
}
```

Response:
```json
{
  "status": "success",
  "version": "v2",
  "processing_time_ms": 45,
  "features": {
    "cross_base_age_marital_gambling_all": 1,
    "ratio_applist_highrisk_apps_all": 0.35
  }
}
```

### 批量计算（支持回测）

```bash
POST /api/v1/calculate_batch
```

Request:
```json
{
  "samples": [
    {"order_id": "...", "raw_data": {...}},
    ...  # 几千到几万条
  ],
  "batch_size": 100
}
```

Response:
```json
{
  "status": "processing",
  "job_id": "batch_20260504_180530_abc123"
}
```

查询进度:
```bash
GET /api/v1/batch_status/batch_20260504_180530_abc123
```

获取结果:
```bash
GET /api/v1/batch_results/batch_20260504_180530_abc123
```

## 版本管理

### 版本信息结构

```json
{
  "version": "v2",
  "timestamp": "2026-05-04T19:35:30",
  "passed_features": ["feature_1", "feature_2"],
  "total_features": 2,
  "total_evaluated": 20,
  "thresholds": {
    "iv": 0.02,
    "psi": 0.25,
    "coverage": 0.05
  },
  "metrics": {
    "avg_iv": 0.045,
    "avg_psi": 0.12
  }
}
```

### 回滚机制

- `latest`软链接始终指向当前使用版本
- 回滚只改变软链接，不删除旧版本
- 可随时回滚到任意历史版本

## 商业化预留

### API密钥管理（暂未实现）

```bash
POST /api/v1/auth/key
{
  "api_key": "sk_live_abc123...",
  "plan": "trial",  # trial / pro / enterprise
  "rate_limit": 1000  # 次/天
}
```

### 监控指标（暂未实现）

- 请求次数
- 响应时间
- 错误率
- API密钥使用统计

## 相关文件

- `agents/feature_deployment_agent.py` - 主实现
- `outputs/deployment/` - 部署包输出
- `outputs/evaluation/passed_features.json` - 输入（通过评估的特征）
- `outputs/feature_code/features_calculator_v2.py` - 输入（完整特征代码）

## 下一步

- [ ] 集成到主Agent流程（orchestrator）
- [ ] 实现API密钥认证
- [ ] 添加监控和日志
- [ ] 前端测试页面
