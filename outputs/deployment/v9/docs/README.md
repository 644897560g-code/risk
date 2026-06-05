# 特征计算服务部署包

**版本**: v9
**生成时间**: 2026-06-04 11:24:21
**特征数**: 320

## 快速开始

### 方式1: Docker Compose（推荐）

```bash
cd v9
docker-compose up -d

# 测试
curl http://localhost:8000/
curl -X POST http://localhost:8000/api/v1/calculate \
  -H "Content-Type: application/json" \
  -d @../examples/test_sample.json
```

### 方式2: 直接运行

```bash
cd v9
pip install -r requirements.txt
python api/app.py
```

## API文档

### 单样本计算
```
POST /api/v1/calculate
Content-Type: application/json

{
  "order_id": "id002...",
  "apply_time": "2026-03-09 10:00:00",
  "raw_data": {...}
}
```

### 批量计算
```
POST /api/v1/calculate_batch
Content-Type: application/json

{
  "samples": [...],
  "batch_size": 100
}
```

## 版本历史

查看 `CHANGELOG.md`

## 技术支持

- 问题反馈: 查看 logs/ 目录
- API文档: http://localhost:8000/docs
