# 特征部署Agent需求规格

**日期**: 2026-05-04
**阶段**: Week 7

---

## 一、核心目标

将**通过评估筛选**的特征代码打包成可部署的生产环境包，供：
1. **风控团队**私有化部署（离线包）
2. **自己**在线SaaS服务（前端测试、Demo演示、未来商业化）

---

## 二、输入输出

### 输入
- 通过评估的特征列表：`outputs/evaluation/passed_features.json`
- 完整特征代码：`outputs/feature_code/features_calculator_v2.py`

### 输出
部署包：`outputs/deployment/deployment_v{N}_YYYYMMDD_HHMMSS/`

```
deployment_package/
├── core/                # 核心计算引擎（裁剪后）
├── api/                 # API服务
├── config/              # 运行时配置
├── deploy/              # Docker部署文件
├── docs/                # 文档
├── tests/               # 测试
├── examples/            # 示例
└── requirements.txt
```

---

## 三、关键特性

### 3.1 版本管理

每次部署生成新版本：
```
outputs/deployment/
├── deployment_v1_20260504_180000/
├── deployment_v2_20260505_120000/
├── deployment_v3_20260506_090000/  ← 当前
└── latest -> deployment_v3_20260506_090000  (软链接)
```

**版本信息** (`config/version.json`):
```json
{
  "version": "v3",
  "timestamp": "2026-05-06T09:00:00",
  "passed_features": ["cross_base_age_marital_gambling_all", ...],
  "total_features": 15,
  "total_evaluated": 20,
  "metrics": {"avg_iv": 0.045, "avg_psi": 0.12}
}
```

**回滚命令**:
```bash
python agents/feature_deployment_agent.py --list-versions
python agents/feature_deployment_agent.py --rollback v2
```

---

### 3.2 双模式部署

| 模式 | 说明 | 目标 |
|------|------|------|
| **A. 私有化部署** | 离线部署包 (tar.gz) | 风控团队内网部署 |
| **B. 在线SaaS** | 自动启动Docker容器 | 前端测试/Demo/商业化 |

---

### 3.3 API设计

#### 单样本计算
```python
POST /api/v1/calculate
Request:
{
  "order_id": "id002luzt202603090951432723072",
  "apply_time": "2026-03-09 10:00:00",
  "raw_data": {...}
}

Response:
{
  "status": "success",
  "version": "v3",
  "processing_time_ms": 45,
  "features": {
    "cross_base_age_marital_gambling_all": 1,
    "ratio_applist_highrisk_apps_all": 0.35
  }
}
```

#### 批量计算（支持回测）
```python
POST /api/v1/calculate_batch
Request:
{
  "samples": [
    {"order_id": "...", "raw_data": {...}},
    ...  # 几千到几万条
  ],
  "batch_size": 100
}

Response:
{
  "status": "processing",
  "job_id": "batch_20260504_180530_abc123"
}

# 查询进度
GET /api/v1/batch_status/{job_id}
Response:
{
  "status": "processing",
  "progress": 45.2,
  "total": 10000,
  "processed": 4520
}

# 获取结果
GET /api/v1/batch_results/{job_id}
Response:
{
  "status": "completed",
  "results": [
    {"order_id": "...", "features": {...}},
    ...
  ]
}
```

---

### 3.4 商业化预留

**API密钥管理**:
```python
POST /api/v1/auth/key
{
  "api_key": "sk_live_abc123...",
  "plan": "trial",  # trial / pro / enterprise
  "rate_limit": 1000  # 次/天
}
```

**监控**:
- 请求次数
- 响应时间
- 错误率
- API密钥使用统计

---

## 四、技术实现

### 4.1 代码裁剪
只保留通过筛选的特征计算方法，移除未通过的，减小部署包体积。

### 4.2 Docker配置
- `Dockerfile`: 镜像构建
- `docker-compose.yml`: 单机部署
- `docker-compose.prod.yml`: 生产环境配置

### 4.3 自动部署
运行部署Agent后：
1. 裁剪代码
2. 生成部署包
3. 构建Docker镜像
4. 启动容器（开发环境）
5. 生成风控部署包（生产环境，压缩）

---

## 五、任务列表

| 任务 | 说明 |
|------|------|
| 核心打包功能 | 裁剪代码、生成部署包、版本管理 |
| 双模式API服务 | 单样本计算、批量计算 |
| 版本管理和回滚 | 版本列表、回滚、当前版本 |
| Docker配置和文档 | Dockerfile、文档 |
| 集成主Agent | orchestrator集成 |

---

## 六、使用场景

### 风控团队
```bash
# 解压部署包
tar -xzf deployment_v1.tar.gz

# 部署
cd deployment_v1
docker-compose up -d

# 测试
curl http://localhost:8000/api/v1/calculate -d @test_sample.json
```

### 在线SaaS
```bash
# 自动启动
python agents/feature_deployment_agent.py

# 访问
# API: http://localhost:8000/api/v1/calculate
# 前端测试: http://localhost:3000/test
```

---

## 七、相关文件

- `agents/feature_deployment_agent.py` - 主实现
- `outputs/deployment/` - 部署包输出
- `outputs/evaluation/passed_features.json` - 输入
- `outputs/feature_code/features_calculator_v2.py` - 输入
