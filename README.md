# 印尼现金贷风险特征挖掘Agent系统

## 项目目标

开发一个面向**印尼市场短期现金贷业务**的风险特征挖掘Agent系统，包含六个核心Agent：

1. **数据分析Agent** - 分析客户申请信息（base信息、applist、FDC数据）和贷后好坏表现，形成业务专有领域知识
2. **特征设计Agent** - 基于数据分析结果、印尼现金贷常识和FDC特征变量清单，设计新增特征指标
3. **特征工程Agent** - 根据特征设计结果开发特征计算代码
4. **特征工程审核Agent** - 审核特征代码语法合法性和逻辑正确性
5. **特征评估Agent** - 计算IV、PSI、覆盖率，筛选优质特征，输出HTML报告
6. **特征部署Agent** - 将保留的特征代码打包供风控团队部署

## 技术栈

- **语言**: Python 3.10+
- **LLM模型**: qwen3.6-plus
- **数据处理**: pandas, numpy
- **报告生成**: Jinja2, HTML
- **可视化**: matplotlib, seaborn, plotly

## 项目结构

```
risk-agent-cc-indo/
├── agents/                     # Agent核心代码
│   ├── base_agent.py          # Agent基类
│   ├── data_analysis_agent.py # 数据分析Agent
│   ├── feature_design_agent.py # 特征设计Agent
│   ├── feature_engineering_agent.py # 特征工程Agent
│   ├── feature_review_agent.py # 特征审核Agent
│   └── feature_evaluation_agent.py # 特征评估Agent
├── data/                       # 数据处理
│   └── data_loader.py         # 数据加载器
├── utils/                      # 工具类
│   └── llm_client.py          # LLM客户端
├── configs/                    # 配置文件
│   └── model_config.yaml      # LLM配置
├── outputs/                    # 输出目录
├── tests/                      # 测试
├── requirements.txt            # 依赖
└── main.py                     # 主入口
```

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行系统

```bash
python main.py
```

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

## 开发计划

| Week | 里程碑 |
|------|--------|
| 1 | 基础设施就绪与数据准备 |
| 2 | 数据分析Agent开发 |
| 3 | 特征设计Agent开发 |
| 4 | 特征工程Agent开发 |
| 5 | 特征审核Agent开发 |
| 6 | 特征评估Agent开发 |
| 7 | 特征部署Agent开发 |
| 8 | 集成测试与优化 |

## 联系方式

- 项目负责人: 石永亮
- 风控对接人: 王栋
