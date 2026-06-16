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

### PostgreSQL 18 测试环境迁移（2026-06-09）

**状态**: ✅ 已完成

- [x] 明确迁移策略：完全去掉 SQLite，不迁移本地 SQLite 历史数据，用户重新注册
- [x] 新增迁移计划文档：`docs/POSTGRESQL_18_MIGRATION_PLAN.md`
- [x] 后端数据库连接改为必须从 `DATABASE_URL` 环境变量或 `.env` 读取：`backend/app/config.py`
- [x] 移除 SQLite 专用初始化逻辑：`backend/app/database.py`
- [x] 新增 PostgreSQL 依赖和 Alembic 依赖：`backend/requirements.txt`、`requirements.txt`
- [x] 新增 Alembic 配置和初始 schema migration：`alembic.ini`、`backend/migrations/`
- [x] 更新本地/生产 Docker 启动方式，后端启动前执行 `alembic upgrade head`
- [x] 在本机 `pg18` 容器执行 `alembic upgrade head` 验证
- [x] 验证后端 import、健康检查、用户重新注册链路

**验证结果**:
- PostgreSQL 版本: `PostgreSQL 18.4`
- Alembic 当前版本: `20260609_0001`
- 已创建表: `users`、`tasks`、`task_logs`、`feature_versions`、`feature_metrics`、`chat_sessions`、`chat_messages`、`alembic_version`
- 临时后端端口 `18000` 健康检查通过
- 测试用户 `pg_test_user` 注册和登录通过，数据写入 PostgreSQL

### 模板库数据库建模与初始化（2026-06-09）

**状态**: ✅ 已完成

- [x] 新增模板维度表模型：`TemplateDimension`
- [x] 新增模板生命周期表模型：`Template`
- [x] 新增模板审批历史模型：`TemplateReviewHistory`
- [x] 新增被拒模板记忆模型：`TemplateRejectedMemory`
- [x] 新增第二版 Alembic migration：`20260609_0002_template_library_schema.py`
- [x] 新增平台初始化入口：`scripts/init_project_data.py`
- [x] 新增模板库 seed：`scripts/seeds/seed_template_library.py`
- [x] Docker 后端启动链路增加 `python scripts/init_project_data.py`
- [x] 在本机 PostgreSQL 18 测试库执行第二版 migration 验证
- [x] 执行平台初始化，确认 7 个维度和 16 个 active 模板入库

**验证结果**:
- Alembic 当前版本: `20260609_0002`
- 新增表: `template_dimensions`、`templates`、`template_review_histories`、`template_rejected_memories`
- 初始化导入: 7 个模板维度、16 个 `active` 模板
- 重复执行初始化脚本验证幂等: 第二次执行为 0 新增、7 个维度更新、16 个模板更新

### 前端产品设计闭环优化（2026-06-15）

**状态**: ✅ 已完成

本轮面向产品经理视角调整前端页面，不新增接口和后端逻辑，优先级按“核心流程闭环 ＞ 逻辑合理性 ＞ 用户体验”执行。

- [x] 工作台改为项目闭环视角，突出“项目 → 知识/数据 → 模板 → 生产 → 评估决策 → 部署交付”
- [x] 任务页改为“特征生产”语义，并在完成、失败、模板任务完成后给出下一步产品动作
- [x] 评估页改为上线决策页，增加推荐上线、谨慎观察、不建议上线的分层判断
- [x] 部署页改为版本生命周期视角，明确待业务确认、待技术部署、已发布、回滚/废弃
- [x] 模板页弱化模板审批边界说明，改为副标题口径，不再使用独立提示卡片
- [x] 知识库页明确数据/知识是生产依据，并按样本标签、业务规则、历史反馈组织信息层级
- [x] 导航信息架构改为“平台 → 当前项目 → 项目任务 → 任务结果”层级，评估/部署不再作为侧栏平级菜单
- [x] 任务详情改为结果闭环承载页，包含执行过程、候选特征、评估报告、部署版本、反馈沉淀
- [x] 评估页和部署页改为“结果库”语义，补充所属平台、所属项目、来源任务和结果类型
- [x] 将“数据与知识”拆为“数据源管理”和“知识依据”，明确数据是项目级输入，知识是业务依据
- [x] 新增数据源管理前端原型，展示数据源、Agent数据识别、业务口径确认、质量检查和数据快照
- [x] 补齐数据源管理承接页面：上传文件数据源、新增数据库连接、生成数据快照
- [x] 任务创建改为“选择/生成数据快照”语义，保留文件上传兼容但不再表达为临时任务上传
- [x] 任务、评估、部署补充来源数据快照追溯，字段识别由Agent完成，不向用户展示底层结构对齐细节
- [x] 弱化解释性提示，不再用独立卡片展示模板/知识/数据源边界说明，改为页面副标题、小号文字或状态标签

**交付物**:
- `web-frontend/src/pages/Dashboard.tsx`
- `web-frontend/src/pages/Tasks.tsx`
- `web-frontend/src/pages/Evaluation.tsx`
- `web-frontend/src/pages/Deployment.tsx`
- `web-frontend/src/pages/Templates.tsx`
- `web-frontend/src/pages/Knowledge.tsx`
- `web-frontend/src/pages/DataSources.tsx`
- `web-frontend/src/components/Layout.tsx`
- `web-frontend/src/index.css`
- `web-frontend/src/App.tsx`

**验证结果**:
- `npm run build` 通过
- 本地 `http://127.0.0.1:5174` 已验证工作台、任务、评估、部署、模板、知识库核心页面可渲染
- 已重启旧的 `5173` Vite 进程，确认 `http://127.0.0.1:5173/tasks` 可看到“平台/项目/项目任务”面包屑和新侧栏层级
- 已验证任务详情可看到“结果归属于当前任务”和执行过程、候选特征、评估报告、部署版本、反馈沉淀 tabs
- 已验证 `http://127.0.0.1:5173/data-sources` 可看到数据源管理、Agent数据识别、质量检查和数据快照
- 已验证数据源管理页三个入口可打开：上传文件数据源、新增数据库连接、生成数据快照
- 已验证任务创建弹窗显示“数据快照来源”“上传文件生成新快照”“使用项目已有数据路径生成快照”
- `npm run build` 通过；源码中已无“模板是加工方式”“这里管理业务依据”“字段识别由 Agent”“当前可启动任务”等独立提示文案

### Notion PRD 前端结构试改（2026-06-16）

**状态**: ✅ 已完成

本轮按 Notion PRD 调整前端产品原型，不新增后端接口和算法逻辑，重点修正“平台-项目-任务-结果”层级与业务流程闭环。

- [x] 侧栏改为“平台 / 当前项目 / 辅助工具”三组，平台包含项目列表和模板库，当前项目包含项目概览、数据源、知识、任务、版本与交付
- [x] 项目列表回归平台级项目登记与切换，移除项目创建时的模板启用和复杂 JSON 配置
- [x] 项目概览改为当前项目首页，展示数据就绪、模板可用、最近任务、最新交付版本四类状态，并提供流程动作入口
- [x] 数据源明确为项目级资产，表达文件型/数据库型数据源、字段自动识别、质量检查和任务绑定快照
- [x] 任务创建改为“确认项目 -> 选择数据源 -> 选择/生成快照 -> 填写任务 -> 启动任务”，保留上传文件作为生成项目数据源/快照入口
- [x] 模板库改为平台级模板生命周期，支持待审、已生效、已驳回三种状态，以及通过/驳回、质量校验和审批记录
- [x] 知识页拆分为项目知识和平台知识，明确项目知识不直接进入公共模板库
- [x] 版本与交付提升为当前项目入口，展示版本追溯、版本对比、交付包下载和 API 调用占位
- [x] 智能助理增加当前项目和对话模式，区分当前项目模式与平台模板模式

**交付物**:
- `web-frontend/src/components/Layout.tsx`
- `web-frontend/src/pages/Projects.tsx`
- `web-frontend/src/pages/Dashboard.tsx`
- `web-frontend/src/pages/DataSources.tsx`
- `web-frontend/src/pages/Knowledge.tsx`
- `web-frontend/src/pages/Tasks.tsx`
- `web-frontend/src/pages/Templates.tsx`
- `web-frontend/src/pages/Deployment.tsx`
- `web-frontend/src/pages/Evaluation.tsx`
- `web-frontend/src/pages/AgentChat.tsx`

**验证结果**:
- `npm run build` 通过
- 源码扫描确认已无“项目管理 / 模板资产 / 项目工作台 / 数据源管理 / 知识依据 / 结果交付 / 部署确认”等旧主命名残留
- 本地 `http://127.0.0.1:5174` 已验证项目列表、项目概览、数据源、任务、模板库、知识、版本与交付、智能助理核心页面均可渲染新层级文案

### PRD v2.1 决策辅助型前端优化（2026-06-16）

**状态**: ✅ 已完成

本轮按 `RiskForge_AI_前端优化_PRD_v2.1.md` 执行 P0 原型优化，不新增后端接口和算法逻辑，重点从“业务层级展示”升级为“用户行动流和决策辅助”。

- [x] 信息架构调整为“工作台 / 探索 / 资产 / 交付 / 助手”，并保留旧路由兼容跳转
- [x] 工作台增加双模式入口：发起探索、启动特征工厂，并加入待办区、最近动态和平台洞察
- [x] 实验列表替代任务列表，创建流程改为 4 步向导：选择模式、选择数据、选择策略、确认执行
- [x] 评估报告改为分层决策台，按推荐上线、谨慎观察、不建议上线展示特征业务卡片
- [x] 新增候选特征集页面，支持待确认、已确认、已排除状态和生成交付版本入口
- [x] 数据源页面改为数据版本表达，弱化“快照”技术术语
- [x] 模板库增加效果目录，展示历史效果、使用次数、业务说明和适用场景
- [x] 知识库增加业务规则驱动推荐，展示规则与推荐特征加工方式的关联
- [x] 版本管理补齐技术包、业务说明书、API文档、小流量验证和确认上线动作
- [x] 助手增加快捷指令：解释当前特征、推荐新模板、诊断实验、对比实验

**交付物**:
- `web-frontend/src/App.tsx`
- `web-frontend/src/components/Layout.tsx`
- `web-frontend/src/pages/Dashboard.tsx`
- `web-frontend/src/pages/Tasks.tsx`
- `web-frontend/src/pages/Evaluation.tsx`
- `web-frontend/src/pages/CandidateFeatures.tsx`
- `web-frontend/src/pages/DataSources.tsx`
- `web-frontend/src/pages/Templates.tsx`
- `web-frontend/src/pages/Knowledge.tsx`
- `web-frontend/src/pages/Deployment.tsx`
- `web-frontend/src/pages/AgentChat.tsx`
- `web-frontend/src/pages/Login.tsx`

**验证结果**:
- `npm run build` 通过
- 源码扫描确认已无“项目概览 / 任务列表 / 发起特征生产 / 部署确认 / 任务结果 / 数据快照”等核心旧产品文案
- 本地 `http://127.0.0.1:5174` 已验证 `/home`、`/mine/experiments`、`/mine/report`、`/ship/candidates`、`/assets/data`、`/assets/templates`、`/assets/knowledge`、`/ship/versions`、`/copilot` 均可渲染关键文案
- 已验证 `/mine/experiments?create=factory` 可自动打开“创建实验”四步向导

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

### Week 6.5: PostgreSQL 与模板库改造 ✅ 已完成 (2026-06-09)

| 模块 | 状态 | 交付物 |
|------|------|--------|
| PostgreSQL 18 迁移 | ✅ | `alembic.ini`, `backend/migrations/versions/20260609_0001_initial_postgresql_schema.py` |
| 模板库表结构 | ✅ | `backend/models/template.py`, `backend/migrations/versions/20260609_0002_template_library_schema.py`, `backend/migrations/versions/20260609_0003_add_template_python_code.py` |
| 项目初始化数据 | ✅ | `scripts/init_project_data.py`, `scripts/seeds/seed_template_library.py`；支持 active 模板和历史 channel2 pending 模板幂等导入 |
| 模板库运行时单写 DB | ✅ | `backend/services/template_library.py`, `backend/routers/templates.py`, `backend/routers/agents.py`, `backend/routers/agent_chat.py`, `backend/services/knowledge_extractor.py`, `backend/services/task_service.py`, `agents/feature_development_agent.py`, `agents/feature_orchestrator.py`, `agents/template_generation_agent.py` |

**说明**:
- `outputs/feature_templates/channel1_templates.json` 只作为初始化 seed 来源，不再作为运行时模板库。
- 历史通道2待审批 seed 已归档到 `scripts/seeds/fixtures/channel2_pending.seed.json`，只作为一次性迁移输入。
- 通道2待审批、审批通过、拒绝记忆、知识抽取入库、AgentChat 触发模板创建，均统一写入 PostgreSQL。
- 不再维护运行时 `channel2_pending.json` / `promoted_templates.json` 这类模板生命周期双写文件。

### Week 6.6: 项目关联与项目模板选择 ✅ 已完成 (2026-06-10)

| 模块 | 状态 | 交付物 |
|------|------|--------|
| 项目表结构 | ✅ | `backend/models/project.py`, `backend/migrations/versions/20260610_0004_project_scoping.py` |
| 默认项目初始化 | ✅ | `scripts/init_project_data.py`, `backend/services/project_service.py` |
| 任务/结果项目关联 | ✅ | `tasks.project_id`, `feature_versions.project_id`, `feature_metrics.project_id` |
| 项目模板选择 | ✅ | `project_templates` 表，`backend/routers/projects.py` |
| API 接入 | ✅ | `/api/projects`, `/api/tasks?project_id=`, `/api/features/versions?project_id=` |
| 前端项目上下文 | ✅ | `web-frontend/src/store/projectStore.ts`, 顶部项目选择器，任务创建/列表绑定当前项目 |
| 项目模板前端配置 | ✅ | `web-frontend/src/pages/Projects.tsx` 创建/编辑项目时选择启用模板 |

**说明**:
- 现有历史数据统一挂到 `默认项目(id=1)`。
- 模板库仍是平台级资产，项目通过 `project_templates` 选择启用哪些 active 模板。
- 任务创建未传 `project_id` 时自动归属默认项目，兼容旧前端。
- 前端当前已完成项目选择、新建/编辑/软删除项目、任务按项目过滤、项目创建/编辑时选择启用模板。
- 知识库 scope 尚未拆分为 platform/project，下一步需要单独建模和接入前端。

### Week 6.7: 内置模板与项目动态模板生成边界 ✅ 已完成 (2026-06-11)

| 模块 | 状态 | 交付物 |
|------|------|--------|
| 内置模板边界 | ✅ | `agents/feature_mass_producer.py`；`T001-T016` 固定作为内置模板组合 |
| 项目动态模板接入 | ✅ | `agents/feature_orchestrator.py`；项目启用的 active `T017+` 模板按 `parameter_space` 进入本次生成组合 |
| 任务项目传参 | ✅ | `backend/routers/tasks.py`, `backend/celery_tasks/agent_tasks.py` |
| 动态模板元数据 | ✅ | `outputs/feature_code/feature_metadata.json` 随本次组合表同源生成 |

**说明**:
- `PARAM_COMBOS` 不再作为所有模板的唯一事实来源，只承载内置 `T001-T016`。
- 通道2晋升后的模板仍先成为平台 active 模板，只有项目在 `project_templates` 启用后才进入该项目的批量挖掘。
- 当前动态模板不再按模板名写死适配；优先使用 `parameter_space.values/enum/options/choices` 展开，缺少显式取值时使用参数名级安全默认值。其他 `T017+` 模板仍建议在 `parameter_space` 中沉淀可执行取值规范。

### Week 6.8: 前端产品化页面优化 ✅ 已完成 (2026-06-12)

| 模块 | 状态 | 交付物 |
|------|------|--------|
| 信息架构升级 | ✅ | `web-frontend/src/components/Layout.tsx`, `web-frontend/src/App.tsx`；导航按平台管理、当前项目、任务结果、辅助工具分组，明确项目是平台级管理对象，任务属于项目，评估和部署是任务结果 |
| 工作台 | ✅ | `web-frontend/src/pages/Dashboard.tsx`；展示项目、模板、通过特征、最新版本、业务流程和最近任务 |
| 模板资产 | ✅ | `web-frontend/src/pages/Templates.tsx`；支持 active/pending 模板列表、模板类型分布、详情、批准/拒绝入口，模板只表达数据加工方式，不展示历史表现指标 |
| 评估报告 | ✅ | `web-frontend/src/pages/Evaluation.tsx`, `web-frontend/src/types/feature.ts`, `web-frontend/src/services/mockData.ts`；按版本展示 IV/PSI/覆盖率图表、特征明细、特征逻辑、输入字段和加工口径 |
| 部署版本 | ✅ | `web-frontend/src/pages/Deployment.tsx`；展示推荐版本、交付检查、历史版本和部署包下载入口 |
| 生产任务体验 | ✅ | `web-frontend/src/pages/Tasks.tsx`；新建任务改为“发起特征生产”产品向导，强化数据、模板、生产、评估、部署流程 |
| 全局样式 | ✅ | `web-frontend/src/index.css`, `web-frontend/src/components/Layout.tsx`；升级为暗色科技风格，新增网格背景、玻璃卡片、霓虹边线、暗色表格、高亮按钮，并修正弹层、抽屉、下拉、分页、Tag、空状态、图表文字等暗色细节配色 |
| 智能助理体验 | ✅ | `web-frontend/src/pages/AgentChat.tsx`, `web-frontend/src/components/ChatMessage.tsx`, `web-frontend/src/components/ChatInput.tsx`；升级为 Copilot 控制台视觉，强化实时推理、模板联动和对话工作区 |
| 前端原型剥离 | ✅ | `web-frontend/src/store/authStore.ts`, `web-frontend/src/services/mockData.ts`, `web-frontend/src/services/api.ts`；取消登录阻断，后端不可用时使用本地演示数据 |

**验证结果**:
- `npm run build` 通过，已生成新的 `web-frontend/dist/` 产物。
- `lsof -nP -iTCP:5174 -sTCP:LISTEN` 确认前端服务正在监听 `127.0.0.1:5174`。
- 本地浏览器插件本次因安全策略拒绝访问 `http://127.0.0.1:5174`，未进行浏览器截图验证。

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
