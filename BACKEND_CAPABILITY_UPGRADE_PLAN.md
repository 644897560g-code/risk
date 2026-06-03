# 后端核心能力升级计划

**目标**: 稳定产出**500个高质量特征**，支持**Docker部署**
**日期**: 2026-05-04

---

## 一、现状分析

### 当前能力
- ✅ 6个Agent独立运行
- ✅ 可产出20个特征（测试级别）
- ✅ 基于短链数据和Label Excel
- ✅ 特征评估和筛选（IV/PSI/覆盖率）
- ✅ 部署Agent创建部署包

### 需要升级的能力

#### 1. 规模化能力
**当前**: 20个特征
**目标**: 500个特征

**差距**:
- 特征设计Agent需要生成更全面的特征方案
- 特征工程Agent需要自动化批量生成代码
- 评估Agent需要处理更大规模数据

#### 2. 特征质量
**当前**: 基础特征
**目标**: 高质量、多样化特征

**方向**:
- 深度挖掘FDC数据（信用报告）
- 复杂的交叉特征
- 时序特征
- 行为特征

#### 3. 工业级可靠性
**当前**: 脚本式
**目标**: 生产级系统

**需求**:
- 完整的错误处理
- 日志系统
- 监控告警
- 容错重试
- 性能优化

#### 4. 部署便利性
**当前**: 手动执行脚本
**目标**: Docker一键部署

**需求**:
- Docker镜像构建
- docker-compose编排
- 配置管理
- 环境变量支持

---

## 二、升级策略

### 2.1 特征数量扩展：20 → 500

#### 策略A: 特征设计Agent升级

**当前设计思路**:
- 基于人工经验设计
- 逐个特征设计
- 主要关注applist

**升级方案**:
1. **系统化特征生成**:
   - 基于FDC变量自动生成派生特征
   - 基于applist自动生成组合特征
   - 基于base信息的交叉特征

2. **特征模板化**:
   ```python
   # 模板1: RFM特征
   for period in [3, 7, 30, 90]:
       for metric in ['count', 'sum', 'avg', 'max']:
           generate_feature(f"ratio_fdc_loan_{metric}_{period}d")

   # 模板2: 交叉特征
   for app_category in ['gambling', 'cash_loan', 'fintech']:
       for base_field in ['age', 'gender', 'salary', 'marriage']:
           generate_feature(f"cross_base_{base_field}_{app_category}")

   # 模板3: 时序特征
   for period in [1, 3, 7, 30, 90]:
       generate_feature(f"trend_applist_install_{period}d")
   ```

3. **FDC数据深度挖掘**:
   - pinjaman记录分析（贷款历史）
   - history_inquiry分析（查询历史）
   - platform_aktif分析（活跃平台）
   - 逾期模式挖掘

#### 策略B: 特征工程Agent升级

**当前实现**:
- 手动编写每个特征的计算逻辑

**升级方案**:
1. **代码自动生成**:
   ```python
   # 基于特征设计文档，自动生成代码框架
   def generate_feature_code(feature_design):
       template_map = {
           'ratio': RATIO_TEMPLATE,
           'count': COUNT_TEMPLATE,
           'cross': CROSS_TEMPLATE,
           'trend': TREND_TEMPLATE,
       }

       template = template_map[feature_design['type']]
       code = template.render(feature_design)
       return code
   ```

2. **批量处理优化**:
   - 向量化计算（pandas）
   - 并行处理（multiprocessing）
   - 缓存中间结果

#### 实施计划

**Week 1**: 特征设计Agent升级
- Day 1-2: 设计特征模板系统（20+模板）
- Day 3-4: FDC深度挖掘逻辑
- Day 5: 自动化生成500个特征设计方案

**Week 2**: 特征工程Agent升级
- Day 1-3: 代码自动生成引擎
- Day 4-5: 性能优化（向量化）

**Week 3**: 验证和优化
- Day 1-3: 小规模测试（50个样本）
- Day 4-5: 调优和修复

---

### 2.2 特征质量提升

#### 当前特征类型
1. applist统计特征
2. FDC基础特征
3. 交叉特征（少）

#### 目标特征体系（500个）

**类别1: Applist特征** (150个)
- 基础统计：安装总数、活跃数、更新时间
- 风险APP占比：赌博/借贷/克隆应用
- 类别多样性：安装类别数、Top3占比
- 时序趋势：近几天安装/更新趋势

**类别2: FDC信用特征** (150个)
- 查询历史：近3/7/30天查询次数
- 贷款记录：总笔数、活跃平台数、逾期笔数
- 平台行为：在贷平台数、申请频率
- 借贷趋势： loan增长趋势

**类别3: 交叉特征** (100个)
- base × applist：年龄×APP类别、薪资×风险APP
- base × FDC：性别×借贷次数、地区×逾期
- applist × FDC：风险APP×查询次数

**类别4: 时序特征** (50个)
- 近期vs历史：近7天vs近30天比率
- 增长趋势：安装趋势、查询趋势
- 变化率：借贷增速、逾期增速

**类别5: 高级特征** (50个)
- 行为模式：安装时间分布
- 异常检测：偏离正常范围
- 综合评分：多特征组合评分

#### 质量保障

**1. IV筛选严格**:
- 阈值从0.02提升到0.05
- 只保留强区分度特征

**2. PSI稳定性**:
- 阈值从0.25降低到0.2
- 确保特征稳定

**3. 覆盖率**:
- 阈值从5%提升到10%
- 避免过度稀疏

**4. 特征去重**:
- 相关性分析（correlation > 0.9则移除）
- 信息冗余检测

---

### 2.3 工业级可靠性

#### 当前问题
- 缺少完善的错误处理
- 日志不够详细
- 没有监控
- 失败后难以定位

#### 升级方案

**1. 错误处理**:
```python
try:
    features = calculate_features(data)
except FeatureCalculationError as e:
    logger.error(f"特征计算失败: {e}", exc_info=True)
    save_failed_features(feature_names)
    raise
except Exception as e:
    logger.critical(f"未预期错误: {e}", exc_info=True)
    raise
```

**2. 日志系统**:
```python
# 结构化日志
{
    "timestamp": "2026-05-04T10:00:00",
    "level": "INFO",
    "module": "feature_engineering",
    "message": "完成100个特征计算",
    "duration_ms": 5000,
    "features_count": 100
}
```

**3. 监控指标**:
- 每个Agent执行时间
- 特征计算成功率
- 内存使用情况
- 错误率

**4. 容错机制**:
```python
# 单个特征失败不影响整体
for feature in features:
    try:
        value = calculate(feature, data)
        results.append(value)
    except Exception as e:
        logger.warning(f"特征 {feature} 计算失败，设为NaN")
        results.append(np.nan)
```

**5. 性能优化**:
- 使用pandas向量化操作
- 并行处理（multiprocessing）
- 缓存中间结果（joblib）

---

### 2.4 Docker部署支持

#### 当前状态
- ✅ 部署Agent生成Dockerfile
- ✅ docker-compose.yml
- ❌ 未测试
- ❌ 缺少配置管理

#### 升级需求

**1. Docker镜像优化**:
```dockerfile
FROM python:3.11-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . /app
WORKDIR /app
```

**2. 配置管理**:
```python
# config.py
import os

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///risk_agent.db')
LLM_API_KEY = os.getenv('LLM_API_KEY')
MODEL_NAME = os.getenv('MODEL_NAME', 'qwen3.6-plus')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'info')
```

**3. docker-compose强化**:
```yaml
version: '3.8'

services:
  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=sqlite:///app/data/risk_agent.db
      - LLM_API_KEY=${LLM_API_KEY}
    volumes:
      - ./data:/app/data
      - ./outputs:/app/outputs
      - ./logs:/app/logs
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 1G
```

**4. 一键部署脚本**:
```bash
#!/bin/bash
# deploy.sh

# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 健康检查
sleep 5
curl http://localhost:8000/health || echo "启动中..."

echo "部署完成！"
```

---

## 三、实施时间表

### 第1阶段：特征规模化（Week 1-2）
- Week 1: 特征设计Agent升级（500个方案）
- Week 2: 特征工程Agent升级（自动生成代码）

### 第2阶段：质量提升（Week 3）
- FDC深度挖掘
- 交叉特征开发
- 时序特征开发

### 第3阶段：可靠性（Week 4）
- 错误处理完善
- 日志系统
- 监控指标

### 第4阶段：Docker部署（Week 5）
- Docker镜像优化
- 配置管理
- 部署脚本

**总计**: 5周

---

## 四、验收标准

### 4.1 特征数量
- [ ] 系统可生成500+个特征设计方案
- [ ] 代码实现500+个特征计算
- [ ] 评估后保留100+个高质量特征

### 4.2 特征质量
- [ ] IV >= 0.05 的特征 >= 100个
- [ ] PSI <= 0.2 的特征 >= 100个
- [ ] 覆盖率 > 10% 的特征 >= 100个

### 4.3 可靠性
- [ ] 完整错误处理
- [ ] 结构化日志
- [ ] 监控指标展示

### 4.4 Docker部署
- [ ] 可一键docker-compose up
- [ ] 环境变量配置
- [ ] 健康检查通过

---

## 五、具体任务

### Week 1: 特征设计升级
- [ ] 创建特征模板系统（20+模板）
- [ ] 实现FDC深度解析
- [ ] 实现交叉特征生成
- [ ] 生成500个特征设计方案

### Week 2: 特征工程升级
- [ ] 实现代码自动生成引擎
- [ ] 性能优化（向量化）
- [ ] 并行处理

### Week 3: 质量提升
- [ ] FDC特征深度开发
- [ ] 时序特征开发
- [ ] 特征去重

### Week 4: 可靠性
- [ ] 错误处理
- [ ] 日志系统
- [ ] 监控指标

### Week 5: Docker部署
- [ ] Dockerfile优化
- [ ] docker-compose配置
- [ ] 部署脚本
- [ ] 测试部署

---

## 六、立即开始：Week 1 Day 1任务

目标: **特征设计Agent升级方案设计**

输出文档:
1. 特征模板设计（20+模板）
2. FDC深度挖掘方案
3. 500个特征生成策略

预计时间: 1天

---

你觉得这个计划如何？需要立即开始Week 1的任务吗？还是有其他优先级调整？
