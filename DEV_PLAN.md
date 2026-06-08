# 风险特征挖掘Agent系统开发计划

> **开始时间**: 2026-04-25
> **目标**: 8周内完成六个Agent的开发、测试和集成

---

## 整体架构 (v2.0 - 2026-05-29更新)

### 新架构：特征开发Agent（合并设计+工程）+ Skills

原有六个Agent中的"特征设计"和"特征工程"已合并为**特征开发Agent**，特征审核Agent已移除（由self-review替代）。

**新流程**：
```
数据分析(简化) → 特征开发Agent(设计+工程+self-review) → 特征评估 → 反馈聚合 → 部署
```

**核心变更**：
1. 合并特征设计+特征工程为特征开发Agent（上下文连续，减少跨Agent传递损耗）
2. 删除特征审核Agent（由self-review step + post_hook校验替代）
3. 引入通道1(DSL模板冷启动) + 通道2(LLM推理新模板) 双通道
4. 新增IV/PSI反馈回路（特征评估结果→结构化总结→注入下一轮）
5. Skill注册表 + post_hook校验机制（LLM输出质量自动校验）
6. 通道2→通道1晋升机制（评估通过的新模板可加入模板库）

**Skill体系**：
- skill_template_recall: 通道1模板召回
- skill_param_fill: 参数填充
- skill_dsl_to_python: dsl→python代码生成
- skill_channel2_reasoning: 通道2LLM推理新模板

**关键文件**：
- `agents/feature_development_agent.py` - 合并后的特征开发Agent（新建）
- `agents/skill_registry.py` - Skill注册表+post_hook引擎（新建）
- `agents/feature_orchestrator.py` - 主协调Agent（v2.0重构）
- `agents/stepwise_framework_design.py` - 三阶段设计框架（保留复用）

**代码整理说明（2026-06-08）**：
- 历史一次性数据处理/调试脚本已归档到 `scripts/one_off/`
- 旧版分离式Agent实现已归档到 `agents/legacy/`
- 在线/离线APP分类模块仍保留在 `data/`，详见 `data/APP_CLASSIFICATION_README.md`

---

## 第一阶段：基础设施与数据准备（Week 1）

**状态**: ✅ 已完成 (2026-04-25)

### 1.1 项目结构

- [x] `agents/` - Agent核心代码目录
- [x] `data/` - 数据处理模块
- [x] `utils/` - 工具类
- [x] `configs/` - 配置文件
- [x] `outputs/` - 输出目录（含子目录）
- [x] `tests/` - 测试文件
- [x] `logs/` - 日志目录

### 1.2 依赖安装

- [x] pandas, numpy - 数据处理
- [x] openai - LLM调用（兼容qwen）
- [x] jinja2 - 模板引擎
- [x] matplotlib, seaborn, plotly - 可视化
- [x] openpyxl - Excel读取
- [x] pyyaml - 配置解析
- [x] requests - HTTP请求

### 1.3 LLM客户端封装 (`utils/llm_client.py`)

- [x] `LLMClient` 类 - 封装qwen3.6-plus调用
- [x] 支持流式输出、错误重试
- [x] Prompt模板管理
- [x] 配置加载功能
- [x] 便捷函数 `create_llm_client()`

### 1.4 数据加载器 (`data/data_loader.py`)

- [x] `ShortLinkFetcher` - 短链数据获取
  - [x] 单条URL获取JSON
  - [x] 批量获取
- [x] `DataLoader` - 统一数据加载
  - [x] 加载短链文件 (2915条)
  - [x] 加载建模样本Excel (2272行)
  - [x] 加载FDC变量清单 (4710个)
  - [x] 加载样例JSON
  - [x] 合并样本与标签

### 1.5 Agent基类 (`agents/base_agent.py`)

- [x] 抽象基类 `BaseAgent`
- [x] 通用功能：保存/加载输出
- [x] 日志记录
- [x] 抽象方法 `run()`

### 1.6 配置文件

- [x] `configs/model_config.yaml` - LLM配置
  - [x] 模型、API、温度参数
  - [x] 各Agent独立配置

### 1.7 主入口与文档

- [x] `main.py` - 程序入口
- [x] `README.md` - 项目说明
- [x] `CLAUDE.md` - Agent开发指南

**交付物**:
- 完整项目结构
- 可运行的基础框架
- 数据加载工具
- LLM客户端

---

## 第二阶段：数据分析Agent开发（Week 2）

**状态**: ✅ 已完成 (2026-04-26)

### 2.1 输入数据

- [x] 短链获取订单申请JSON
- [x] 好坏关联标签

### 2.2 核心功能模块

- [x] 基础信息分析模块
  - [x] 用户画像统计（年龄、性别、职业、收入等）
  - [x] 各维度与逾期相关性
  - [x] WOE编码

- [x] 应用列表分析模块
  - [x] 应用类型分布
  - [x] 应用数量与逾期关系
  - [x] 高风险应用识别
  - [x] 安装时长分析

- [x] FDC数据分析模块
  - [x] 历史查询次数统计
  - [x] 近3/7/30天查询频率
  - [x] 贷款记录分析
  - [x] 活跃平台数
  - [x] DPD分布

### 2.3 完整应用清单提取（已完成）

**应用来源分类** (2026-04-25):
- [x] 从2272个有标签样本（626好客户 + 1646坏客户）成功提取应用
- [x] 完整应用总数: **11,851个**去重应用
  - 好客户独有: **2,147个** (outputs/app_analysis/good_customer_apps_complete.csv)
  - 坏客户独有: **6,892个** (outputs/app_analysis/bad_customer_apps_complete.csv)
  - 共有应用: **2,812个** (outputs/app_analysis/common_apps_complete.csv)

### 2.4 LLM科学分类（已完成）

**分类方案设计** (2026-04-26):
- [x] 15个标准类别定义
- [x] 类别优先级规则
- [x] Prompt优化: 包含示例、判断原则
- [x] 测试验证: 20个样本测试通过

**全量分类执行** (2026-04-26):
- [x] 分批配置: 每批200个应用，共60批次
- [x] 分类完成: **11,850个应用** (99.99%成功率)
- [x] 高风险类别识别: 1,022个 (gambling 561, cash_loan 262, fintech_lending 116, fake_gps 29, clone_app 28, app_store 26)
- [x] 输出文件:
  - outputs/app_analysis/classification_complete_11850.json (1.6MB)
  - outputs/app_analysis/classification_statistics.json
  - outputs/app_analysis/app_classification_complete.csv

### 2.5 输出：业务知识库

- [x] JSON格式知识库 (已整合11,850个应用的分类结果)
- [x] 包含15个类别定义、优先级规则、高风险类别统计

**交付物**:
- `agents/legacy/data_analysis_agent.py`（2026-06-08已归档，历史数据分析Agent）
- `outputs/knowledge_base/knowledge_base.json`
- `scripts/one_off/batch_classify_all_apps.py` (2026-06-08已归档，历史全量APP分类脚本)
- `outputs/app_analysis/good_customer_apps_complete.csv` (新增)
- `outputs/app_analysis/bad_customer_apps_complete.csv` (新增)
- `outputs/app_analysis/common_apps_complete.csv` (新增)
- `outputs/app_classification/test_20_apps.csv` (新增)
- `outputs/app_classification/test_20_result.json` (新增)

**关键修复与增强** (2026-04-25):
- 修复了analyze_with_llm()方法，仅发送统计摘要而非原始JSON数据
- Token消耗降低约98%（从~500K降至~10K）
- 添加了token估算日志记录
- **全量样本应用分析**: 基于2272条有好坏标签的短链数据完成好坏客户应用对比
  - 好客户626个，坏客户1646个（逾期率72.45%）
  - 发现11851个独立应用，好客户独有2147个，坏客户独有6892个，共有2812个
- **LLM科学分类设计** (2026-04-26):
  - 15个标准类别体系
  - 类别优先级规则（高风险>金融>通用>兜底）
  - 20个样本测试通过
- **批量分类方案**: 每批200个应用，带重试机制和中间结果保存

---

## 第二阶段补充：在线APP分类模块（2026-05-02完成）

**状态**: ✅ 已完成

### 核心功能

实现了**两级分类 + 夜间批量补充**的在线分类流程：

1. **第一级：缓存查询** - 快速匹配11,850个已知APP
2. **第二级：规则引擎** - 基于LLM生成的规则实时判定新APP
3. **夜间批量** - unknown APP凌晨2点批量调用LLM分类

### 交付物

- `data/rule_engine_classifier.py` - 规则引擎分类器
- `data/batch_classify_new_apps.py` - 夜间批量分类器
- `scripts/run_batch_classification.sh` - 定时执行脚本
- `scripts/setup_cron.sh` - 定时任务配置工具
- `outputs/risk_rules/online_app_classification_rules_llm.json` - LLM规则库（生成中）
- `outputs/risk_rules/online_app_classification_rules_llm_summary.md` - 规则摘要

### 技术特点

| 特性 | 说明 |
|------|------|
| **规则来源** | LLM从11,850个已分类样本学习 |
| **规则数量** | 16个类别（排除other兜底类别） |
| **样本使用** | 每个类别使用全部样本（最多200个） |
| **正则描述** | 每个正则都有中文说明 |
| **分类置信度** | 0.7-1.0，低于0.7标记为unknown |
| **批量策略** | 每批50个APP，结果回写缓存 |

---

## 第三阶段：特征设计Agent开发（Week 3）

**状态**: ✅ 已完成 (2026-05-04)

### 3.1 输入数据

- [x] 业务知识库JSON
- [x] FDC4710变量清单

### 3.2 核心功能模块

- [x] 特征去重检查（编辑距离算法）
- [x] 基于业务知识设计新特征
- [x] 特征类型：计数、比例、极值、时间间隔、交叉

### 3.3 输出：特征设计文档

- [x] JSON格式设计文档 (`outputs/feature_design/feature_design_doc.json`)
- [x] 每个特征：名称、业务解释、设计理由

**交付物**:
- `agents/legacy/feature_design_agent.py` - 旧版特征设计Agent（2026-06-08已归档）
- `outputs/feature_design/feature_design_doc.json` - 20个特征设计
- `outputs/feature_design/FEATURE_DESIGN_SUMMARY.md` - 设计总结

**设计结果统计**:
- 总特征数: 20个
- 按类型: count(8), ratio(7), cross(2), avg(1), max(1), time_gap(1)
- 按数据源: applist(9), fdc(7), base(4)
- 预期相关性: positive(18), negative(2)

---

## 第四~五阶段（合并）：特征开发Agent + Skills（2026-05-29重构）

**状态**: ✅ 已完成 (2026-05-29)

### 架构变更说明

**合并原因**：
- 特征设计和特征工程拆成两个独立Agent导致上下文不连续
- 跨Agent传递设计文档有信息损耗，导致审核不通过时反复打回
- 通道2（LLM推理新模板）需要"设计+工程"在同上下文中完成

**移除特征审核Agent原因**：
- 语法检查、防穿越检查已被post_hook覆盖
- "设计和实现是否一致"问题在合并后不再存在
- 冗余检测、参数异常检测暂无强需求

### 核心交付物

- [x] `agents/feature_development_agent.py` - 合并后的特征开发Agent
  - [x] 三阶段风险驱动设计（复用stepwise_framework_design）
  - [x] IV/PSI反馈注入（从iv_psi_feedback_rN.json读取）
  - [x] 代码生成（LLM→FeatureCalculator类）
  - [x] Self-review（生成后整体审视）
  - [x] 通道1 4个Skill函数（模板召回/参数填充/dsl→python/通道2推理）

- [x] `agents/skill_registry.py` - Skill注册表+post_hook引擎
  - [x] SkillResult数据类
  - [x] Skill注册机制
  - [x] post_hook执行引擎（可重试/不可重试）
  - [x] 重试循环（最多3次）

- [x] `agents/feature_orchestrator.py` - v2.0重构
  - [x] 5步流程：数据分析→特征开发→特征评估→反馈聚合→部署
  - [x] 移除特征审核Agent
  - [x] 新增反馈聚合步骤（iv_psi_feedback_rN.json）

### 待完成的后续阶段

- 通道1模板标准化（25个模板→T001-T025编号）
- 通道2→通道1晋升机制（AUTO_PROMOTE开关）
- post_hook具体check实现
- IV/PSI反馈回路完善（从评估结果自动聚合）

---

## 第七阶段：特征部署Agent开发（Week 7）

**状态**: ✅ 已完成 (2026-05-04)

### 7.1 输入数据

- [x] 通过筛选的特征代码 (features_calculator_v2.py)
- [x] 通过评估的特征列表 (passed_features.json)

### 7.2 核心功能模块

- [x] 代码打包 - 根据通过特征裁剪代码
- [x] 版本管理 - v1/v2/v3版本控制，支持回滚
- [x] API服务 - FastAPI实现（单样本+批量）
- [x] Docker配置 - Dockerfile + docker-compose.yml
- [x] 文档生成 - README + 示例代码 + 测试

### 7.3 输出：部署包

- [x] 特征计算模块 - core/feature_calculator.py
- [x] API服务 - api/app.py
- [x] 配置文件 - config/version.json, config/config.yaml
- [x] Docker文件 - deploy/Dockerfile, deploy/docker-compose.yml
- [x] 文档 - docs/README.md, examples/api_usage.py
- [x] 测试 - tests/test_api.py
- [x] 压缩部署包 - v1.tar.gz (供风控团队)

### 7.4 关键特性

- [x] 版本管理：--list-versions, --rollback
- [x] 双模式部署：私有化部署 + SaaS服务
- [x] 批量计算：异步批量处理，支持回测
- [x] 商业化预留：API密钥管理（trial/pro/enterprise）

**交付物**:
- ✅ `agents/feature_deployment_agent.py` (850行代码)
- ✅ `outputs/deployment/DEPLOYMENT_USAGE.md` (使用指南)
- ✅ `outputs/deployment/DEPLOYMENT_SUMMARY.md` (开发总结)
- ✅ `outputs/deployment/latest -> v1` (当前版本)
- ✅ `outputs/deployment/v1.tar.gz` (离线部署包)
- ✅ 集成到主Agent流程 (feature_orchestrator.py)

---

## 第八阶段：集成测试与优化（Week 8）

**状态**: ✅ 已完成 (2026-05-29)

### 8.1 架构重构完成

- [x] 合并特征设计+特征工程为特征开发Agent
- [x] 移除特征审核Agent
- [x] 引入Skill体系+post_hook机制
- [x] 新增IV/PSI反馈回路框架

### 8.2 代码质量

- [x] 所有新文件语法验证通过
- [x] 导入链和类实例化验证通过
- [x] orchestrator步骤完整性验证通过

---

## 里程碑汇总

| Week | 阶段 | 状态 | 交付物 |
|------|------|------|--------|
| 1 | 基础设施 | ✅ 已完成 (2026-04-25) | 项目框架、数据加载器、LLM客户端 |
| 2 | 数据分析Agent | ✅ 已完成 (2026-04-26) | 业务知识库 + 11,850应用分类 + 规则学习器 |
| 2.5 | 在线APP分类模块 | ✅ 已完成 (2026-05-02) | 规则引擎分类器 + 定时任务 + LLM规则库 + 验证测试 |
| 3-5 | 特征开发Agent + Skills | ✅ 已完成 (2026-05-29) | 合并设计+工程，移除审核Agent，新增Skill体系+post_hook |
| 6 | 特征评估Agent | ✅ 已完成 (2026-05-04) | HTML报告、通过特征列表 |
| 7 | 特征部署Agent | ✅ 已完成 (2026-05-04) | 部署包 |
| 8 | 集成测试+架构重构 | ✅ 已完成 (2026-05-29) | v2.0架构：合并特征开发Agent、Skill体系、反馈回路 |

---

## Web开发计划（6周）

### Week 1: FastAPI后端基础 ✅ 已完成 (2026-05-31)

| 模块 | 状态 | 交付物 |
|------|------|--------|
| 项目结构 | ✅ | backend/ 目录结构 |
| 数据库设计 | ✅ | SQLite初始化、表结构 |
| 核心API | ✅ | 10个API路由：Task CRUD + Agent状态 + Feature版本 + 健康检查 |
| Celery集成 | ✅ | 异步任务队列（run_mass_production + run_feature_evaluation）|

### Week 2: React前端基础 ✅ 已完成 (2026-05-31)

| 模块 | 状态 | 交付物 |
|------|------|--------|
| 项目初始化 | ✅ | Vite + React 18 + TypeScript 项目 |
| 核心组件 | ✅ | Layout、AgentCard、Dashboard等 |
| 路由配置 | ✅ | 页面路由 |
| API服务 | ✅ | Axios封装 + 类型定义 |

### Week 3: Dashboard和任务管理 ✅ 已完成 (2026-05-31)

| 模块 | 状态 | 交付物 |
|------|------|--------|
| Dashboard页面 | ✅ | Agent状态卡片 + 任务列表 |
| 任务管理页面 | ✅ | 筛选 + 分页 + 详情 |
| ECharts可视化 | ✅ | IV分布柱状图、PSI柱状分布、覆盖率饼图 |
| 特征评估页面增强 | ✅ | 可交互图表 + 表格混合视图、折叠面板 |

### Week 4-5: Agent页面开发 ✅ 已完成 (2026-05-31)

| 页面 | 状态 | 交付物 |
|------|------|--------|
| Agent控制台 | ✅ | Agent选择器 + 执行流程Steps + 执行历史 + 日志抽屉 |
| 特征部署 | ✅ | 版本详情 + 部署说明 + 下载按钮 |
| 后端API | ✅ | 新增 6 个路由: run/result/logs |

### Week 5: 可视化增强 ✅ 已完成 (2026-05-31)

| 模块 | 状态 | 交付物 |
|------|------|--------|
| Dashboard图表 | ✅ | ECharts集成（IV/PSI/覆盖率图表） |
| 评估报告可视化 | ✅ | IV分布柱状图、PSI柱状分布、覆盖率饼图 |
| 知识库可视化 | ⏳ | 用户画像图表 |

### Week 6: 测试与优化 🚧 进行中 (2026-05-31)

| 模块 | 状态 | 交付物 |
|------|------|--------|
| 后端测试 | 🔄 | 单元测试 + 集成测试（已建 tests/） |
| 前端测试 | ⏳ | E2E测试 |
| 性能优化 | ⏳ | 代码分割 + 懒加载 |
| API认证 | ⏳ | API Key 鉴权 |
| Docker部署 | ⏳ | docker-compose 全栈 |

---

## Web与Agent开发协调

1. **API先行**: 先定义好API接口，前后端并行开发
2. **Agent优先**: Agent核心逻辑完成后再开发对应前端
3. **Mock数据**: 前端开发时使用Mock数据
4. **渐进集成**: Agent完成一个就集成一个

---

## 关键约束

1. **防穿越**: 特征计算只能用申请时间之前的数据
2. **质量门槛**: IV>=0.02, PSI<=0.25, 覆盖率>5%
3. **特征去重**: 不与FDC4710的4710个特征重复
4. **模型**: 统一使用qwen3.6-plus
5. **异步任务**: 所有Agent任务通过Celery执行
6. **实时更新**: 前端需要实时显示任务进度
