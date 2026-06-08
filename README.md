# 印尼现金贷风险特征挖掘Agent系统

## 项目目标

开发一个面向**印尼市场短期现金贷业务**的风险特征挖掘Agent系统。

当前主流程已经从早期六Agent串行架构演进为：

```
FeatureOrchestrator
  → FeatureDevelopmentAgent(设计+工程+self-review)
  → FeatureEvaluator
  → Feedback Aggregation
  → FeatureDeploymentAgent
```

早期的数据分析、特征设计、特征工程、审核等分离式Agent仍保留在 `agents/legacy/`，仅用于历史复现和参考。

## 技术栈

- **语言**: Python 3.10+
- **LLM模型**: qwen3.6-plus
- **数据处理**: pandas, numpy
- **报告生成**: Jinja2, HTML
- **可视化**: matplotlib, seaborn, plotly

## 项目结构

```
riskforge-ai/
├── backend/                         # FastAPI + Celery 管理后台
├── agents/
│   ├── feature_orchestrator.py      # 当前主协调Agent
│   ├── feature_development_agent.py # 当前特征开发Agent
│   ├── feature_mass_producer.py     # 确定性批量特征生产
│   ├── feature_evaluation_agent.py  # IV/PSI/覆盖率评估
│   ├── feature_deployment_agent.py  # 部署包生成器
│   ├── template_generation_agent.py # 模板生成
│   ├── stepwise_framework_design.py # 保留复用的三阶段设计框架
│   └── legacy/                      # 旧版分离式Agent和历史实验
├── data/
│   ├── data_loader.py               # 数据加载器
│   ├── rule_engine_classifier.py    # 在线APP规则分类器
│   ├── batch_classify_new_apps.py   # 夜间未知APP批量分类
│   └── APP_CLASSIFICATION_README.md # APP分类模块边界说明
├── scripts/
│   ├── run_batch_classification.sh  # APP分类定时任务
│   └── one_off/                     # 一次性数据处理/debug/历史生成脚本
├── outputs/                         # 运行产物、评估报告、部署包快照
├── tests/                           # 测试
├── utils/                           # 工具类
└── DEV_PLAN.md                      # 当前开发计划和断点续做文档
```

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行系统

```bash
python -m backend.app.main
```

批量特征生产入口以 `agents/feature_orchestrator.py` 和 Web/Celery 任务为准；根目录 `main.py` 是早期框架入口，不再代表当前完整主流程。

## 关键业务规则

### 防穿越机制
- 特征计算只能使用用户申请时间之前的信息
- 时间计算要从用户申请时间往前推

### 特征质量门槛
- IV >= 0.02
- PSI <= 0.25
- 覆盖率 > 5%

### 特征去重
- 新增特征不能与FDC4710变量清单中的4710个特征重复
