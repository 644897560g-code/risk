# RiskForge AI — 项目交接文档

> **项目**: 印尼现金贷风险特征挖掘Agent系统
> **交接时间**: 2026年6月
> **移交方**: AI原型开发团队
> **接收方**: 专职开发团队（开发 / 算法 / 产品）

---

## 一、项目总览

### 1.1 项目定位

面向**印尼市场短期现金贷首贷客户**，通过多Agent协作的AI系统，自动完成：

1. **数据分析** — 分析客户申请信息（base/applist/FDC）与好坏表现的相关性
2. **特征设计** — 基于业务知识设计新增风控特征指标
3. **特征工程** — 开发特征计算代码（含防穿越机制）
4. **特征评估** — 计算IV/PSI/覆盖率，筛选高质量特征
5. **部署交付** — 打包为黑盒API，供风控团队线上调用

### 1.2 当前成果

| 指标 | 数值 |
|------|------|
| DSL模板 | 16个确定性模板（T001-T016） |
| 枚举特征总数 | 542个（418主特征 + 124衍生特征） |
| 部署版本 | v9（阿里云硅谷轻量云已部署） |
| 单样本耗时 | ~2s（超时控制1.8s可配） |
| 数据维度 | APP安装行为 / FDC征信记录 / 借贷历史 / 申报信息 |
| 样本规模 | 2916个订单（逾期率72.45%） |
| APP分类 | 11,850个已分类APP，15个类别 |

### 1.3 给不同角色的阅读建议

| 角色 | 重点关注 |
|------|---------|
| 产品团队 | 二(流程)、五(模板三路径)、六(模板与特征设计关系) |
| 算法团队 | 二(流程)、三(数据特殊处理)、七(特征评估)、九(技术债) |
| 开发团队 | 四(目录结构)、五(三路径代码)、八(部署)、十(启动指南) |

---

## 二、系统架构与核心流程

### 2.1 三层架构

```
┌──────────────────────────────────────────────────────────────┐
│                        Web 前端层                             │
│  Tasks(任务管理) │ Knowledge(知识库) │ AgentChat(Agent对话)    │
│  Template(模板审核) │ FeatureCompute(在线计算)                 │
│  React 18 + TypeScript + Ant Design + ECharts + Zustand      │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTP / SSE
┌──────────────────────────▼───────────────────────────────────┐
│                     后端服务层 (FastAPI)                        │
│  routers/ → tasks, features, knowledge, templates, agents     │
│  services/ → knowledge_extractor, task_service                │
│  celery_tasks/ → 异步Agent任务队列                             │
│  models/ → SQLAlchemy (Task, FeatureMetric, ChatSession...)  │
│  auth/ → JWT登录认证                                          │
│  数据库: SQLite (feature_mining.db)                            │
└──────────────────────────┬───────────────────────────────────┘
                           │ 调度
┌──────────────────────────▼───────────────────────────────────┐
│                    Agent 特征挖掘流水线                          │
│                                                                │
│  特征开发Agent (FeatureDevelopmentAgent)                       │
│  ├─ 通道1: DSL模板召回 → 确定性参数展开 → DSL→Python (90%)    │
│  ├─ 通道2: LLM推理新模板 → 人工确认 → 晋升通道1 (创新路径)     │
│  └─ 通道3: 用户知识→提取→模板生成→审核 (知识驱动路径)           │
│                                                                │
│  特征评估Agent (FeatureEvaluator)                              │
│  ├─ 数据划分(train/oot) → Pass1(参考分布) → MassProduce        │
│  └─ Pass2(全量计算) → IV/PSI/覆盖率 → HTML报告+CSV+反馈       │
│                                                                │
│  特征部署Agent (FeatureDeploymentAgent)                        │
│  └─ 打包FeatureCalculator → version.json → Docker部署包       │
│                                                                │
│  IV/PSI反馈回路 → iv_psi_feedback_rN.json → 下一轮特征开发     │
└──────────────────────────┬───────────────────────────────────┘
                           │ 输出
┌──────────────────────────▼───────────────────────────────────┐
│                     部署层 (Docker)                            │
│  阿里云硅谷轻量云 → FastAPI服务 → 8000端口                      │
│  鉴权: X-API-Key Header | 超时: 1.8s | 返回: 529个特征值      │
│  POST /api/v1/calculate → {status, features, processing_time} │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 核心流程（按步骤）

| 步骤 | 模块 | 输入 | 输出 | LLM调用 |
|------|------|------|------|---------|
| 1.创建任务 | 用户/后端 | 任务参数(名称,数据路径,模式) | task DB记录 | 否 |
| 2.数据分析 | data_analysis_agent | 样本数据+标签 | 业务知识结构 | 是 |
| 3.特征开发 | feature_development_agent | 业务知识+历史反馈 | 特征计算代码 | 部分(通道2/自审) |
| 4.特征评估 | feature_evaluation_agent | 特征计算器+样本 | IV/PSI报告+反馈 | 否(纯计算) |
| 5.打包部署 | feature_deployment_agent | 通过的特征代码 | 部署包(v9.tar.gz) | 否 |
| 6.反馈循环 | orchestrator | iv_psi_feedback_rN.json | 下一轮特征开发输入 | 否 |

### 2.3 架构演进（为什么要合并Agent）

本系统经历了三次架构迭代：

**v1（原始6Agent串行）**:
数据分析 → 特征设计 → 特征工程 → 审核Agent → 评估 → 部署
- 问题: LLM调用过多(200万+token/run)、审核循环低效(2-3轮重试)、特征质量不稳定、耗时长

**v2（合并为FeatureDevelopmentAgent）**:
特征开发Agent(含自审) → 评估 → 部署 + IV/PSI反馈回路
- 改进: 减少跨Agent数据传递、自审替代独立审核Agent

**v3（当前: FeatureDevelopmentAgent + Skills框架）**:
Agent控制流 + 确定性Skill(90%) + LLM Skill(10%)
- 核心思路: 把LLM的创意限定在可控范围，非创意步骤用代码锁定

---

## 三、数据层 — 特殊处理规则

### 3.1 数据源总览

| 数据源 | 位置 | 关键字段 | 用途 |
|--------|------|---------|------|
| **base** | params.base | appname, salary, gender, job, workYears, marita, children, birthday | 用户申报信息 |
| **appList** | params.appList | packageX, appName, inTime(安装时间), upTime(更新时间), category(分类后) | 行为风险画像 |
| **FDC inquiry** | params.FDC.history_inquiry | statistic.{3/7/30/90/180/360}_hari, detail(近期查询明细) | 征信查询频次 |
| **FDC pinjaman** | params.FDC.pinjaman[] | tgl_penyaluran_dana, tgl_jatuh_tempo, tgl_pelaporan_data, status_pinjaman(O/L/W/F), kualitas_pinjaman(1/3/5), tipe_pinjaman, nilai_pendanaan, id_penyelenggara | 借贷历史 |
| **好坏标签** | is_overdue | 1=逾期, 0=正常(逾期率72.45%) | 训练目标 |

### 3.2 防穿越机制（核心红线！）

所有特征计算必须遵守：**只能使用用户申请时间之前的数据**。

```python
apply_time_dt = 从orderId中提取的申请时间

_filter_by_time(data, source, apply_time_dt, window_days):
    cutoff = apply_time_dt - timedelta(days=window_days)
```

**三条硬性过滤规则**:

| 规则 | 针对数据 | 实现位置 | 说明 |
|------|---------|---------|------|
| **appList upTime检查** | appList | `channel1_calculators.py:_filter_by_time()` | 只保留 `upTime <= apply_time` 的应用，防止app被卸载后重装的穿越 |
| **FDC上报时间过滤** | FDC pinjaman | 同上(需求1) | `tgl_pelaporan_data`(数据上报时间)必须在申请时间之前，上报时间在申请之后的贷款当时不可用 |
| **逾期类到期过滤** | FDC pinjaman | 同上(需求2) | 逾期相关特征只保留 `tgl_jatuh_tempo_pinjaman <= apply_time_dt`(已到期贷款)，未到期贷款的逾期状态为脏数据 |

### 3.3 APP分类体系

**两级在线分类 + 夜间批量补充**:

```
用户申请 → 提取APP列表
  ↓
第一级: 缓存匹配 (classification_complete_11850.json, 11850个已知APP)
  └→ 未命中 → 第二级: 规则引擎 (online_app_classification_rules_llm.json)
       ├─ 关键词匹配 + 正则 + 品牌白名单
       └→ 仍无法判定 → 标记unknown → 夜间批量LLM分类
```

**15个类别**:
- **高风险(6)**: gambling(赌博), cash_loan(现金贷), fintech_lending, fake_gps(虚拟定位), clone_app(应用克隆), app_store(第三方商店)
- **其他(9)**: banking, ewallet, shopping, transportation, food_delivery, productivity, utility, religious, social_entertainment

**关键文件**:

| 文件 | 说明 |
|------|------|
| `outputs/app_analysis/classification_complete_11850.json` | 11850个APP的完整分类缓存(1.6MB) |
| `outputs/risk_rules/online_app_classification_rules_llm.json` | 规则引擎规则库 |
| `data/rule_engine_classifier.py` | 规则引擎实现类 |
| `data/batch_classify_new_apps.py` | 夜间批量LLM分类脚本 |

### 3.4 FDC数据特殊处理

| 处理 | 说明 | 代码位置 |
|------|------|---------|
| fdc_inquiry使用预聚合值 | 从statistic读取{3/7/30/90/180/360}_hari的计数，构造虚拟记录 | `channel1_calculators.py:_filter_by_time()` |
| fdc_pinjaman 12种cond过滤 | 支持status/kualitas/tipe/syariah多维筛选 | `feature_mass_producer.py` line 37-50 |
| APP类别分组(proportion) | applist按9组分组合并 | `feature_mass_producer.py` line 53-64 |
| FDC proportion目标过滤 | 9种target_cond组合 | `feature_mass_producer.py` line 67-77 |


---

## 四、项目目录结构

```
risk-agent-cc-indo/
│
├── agents/                              ★ Agent核心模块
│   ├── feature_orchestrator.py          主协调Agent - 管理完整流水线
│   ├── feature_development_agent.py      ★ 特征开发Agent(合并设计+工程+自审)
│   │   ├── skill_template_recall()       通道1: 模板召回(代码)
│   │   ├── skill_param_fill()            通道1: 确定性参数展开(代码)
│   │   ├── skill_dsl_to_python()         通道1: DSL→Python(代码)
│   │   ├── skill_channel2_reasoning()    通道2: LLM推理新模板(LLM)
│   │   ├── promote_template()            通道2→通道1晋升(代码)
│   │   └── self_review()                 自审(LLM)
│   ├── feature_evaluation_agent.py      特征评估Agent - IV/PSI/覆盖率+报告
│   ├── feature_deployment_agent.py      部署Agent - 打包特征计算代码
│   ├── feature_mass_producer.py          ★ Mass Producer引擎 - 542特征确定性生成
│   ├── template_generation_agent.py     通道3: 用户知识→模板生成
│   ├── skill_registry.py                ★ Skill注册表+post_hook校验引擎
│   ├── skill_param_design.py            参数设计Skill(旧版，已被确定性展开替代)
│   ├── code_ast_verifier.py             AST代码校验器
│   └── base_agent.py                    Agent基类
│
├── backend/                             Web后端 (FastAPI + SQLite + Celery)
│   ├── app/main.py                      FastAPI应用入口
│   ├── routers/
│   │   ├── tasks.py                     任务CRUD + 特征描述/公式/来源
│   │   ├── features.py                  特征管理 + 部署包下载
│   │   ├── knowledge.py                 知识文件上传/搜索/删除
│   │   ├── templates.py                 模板管理 + 待审核列表
│   │   ├── agent_chat.py                SSE流式Agent对话
│   │   ├── agents.py                    Agent状态/控制端点
│   │   └── auth.py                      JWT登录/注册
│   ├── services/
│   │   ├── knowledge_extractor.py       知识提取(通道3)
│   │   └── task_service.py              任务业务逻辑层
│   ├── celery_tasks/                    Celery异步任务定义
│   ├── models/                          SQLAlchemy模型(Task, FeatureMetric等)
│   ├── schemas/                         Pydantic请求/响应模型
│   ├── auth/                            JWT认证(deps, jwt)
│   └── requirements.txt                 后端依赖
│
├── web-frontend/src/                    前端 (React 18 + TypeScript + Vite)
│   ├── pages/
│   │   ├── Tasks.tsx                    任务管理(核心页面: 计算/评估/部署3个Tab)
│   │   ├── AgentChat.tsx                流式Agent对话(会话侧边栏)
│   │   ├── Knowledge.tsx                知识管理(上传/搜索/预览/统计)
│   │   └── Login.tsx                    登录页
│   ├── components/
│   │   ├── FeatureCharts.tsx            IV/PSI/覆盖率ECharts图表
│   │   ├── TemplateSidebar.tsx          模板待审核侧边栏
│   │   ├── KnowledgePreview.tsx         知识文件预览
│   │   ├── ChatInput.tsx / ChatMessage.tsx  对话组件
│   │   ├── ReviewPanel.tsx              特征审核面板
│   │   └── charts/                      ECharts子组件(IV/PSI热力/覆盖率饼图)
│   ├── constants/
│   │   └── featureDesignFramework.ts    16模板定义常量(给前端展示用)
│   ├── services/api.ts                  Axios API调用层
│   ├── store/authStore.ts               Zustand认证状态
│   └── types/                           TypeScript类型定义
│
├── outputs/                             ★ 所有产出物
│   ├── deployment/                      部署包(v1~v9, latest→v9)
│   │   └── v9/                          v9部署包(API+FeatureCalculator+Docker)
│   ├── evaluation/                      特征评估结果(HTML报告+CSV+IV/PSI反馈)
│   ├── feature_code/
│   │   ├── channel1_calculators.py      通道1计算函数(T001-T015)
│   │   ├── features_calculator_v2.py    完整FeatureCalculator类
│   │   └── orchestrator_state.json      流程状态(断点续做)
│   ├── feature_templates/
│   │   └── channel1_templates.json      16 DSL模板定义
│   ├── app_analysis/                    APP分类缓存(11850个)
│   ├── feature_design/                  特征设计产出
│   ├── risk_rules/                      APP分类规则库
│   └── knowledge_base/                 知识库文件
│
├── data/                                数据文件
│   ├── all_samples/                     2916个订单JSON样本
│   ├── feature_mining.db                SQLite主数据库
│   ├── data_loader.py                   数据加载工具
│   └── rule_engine_classifier.py        APP规则引擎分类器
│
├── utils/llm_client.py                  LLM调用封装(OpenRouter + qwen3.6-plus)
├── configs/                             模型配置
├── prompts/                             Prompt模板
├── scripts/                             部署/定时任务脚本
├── tests/test_backend.py                后端测试(12KB)
│
├── CLAUDE.md                            Claude开发规范
├── DEV_PLAN.md                          开发计划(断点续做核心文档)
├── LESSONS_LEARNED.md                   踩坑记录(约48KB, 必读)
├── AGENT_ORCHESTRATOR_LESSONS.md        主Agent流程指南
├── WEB_ARCHITECTURE.md                  Web架构文档
└── HANDOVER.md                          本文档
```

---

## 五、模板生成的三个路径

### 5.1 路径总览

```
                    ┌──────────────────────────────────────────┐
                    │    特征开发Agent 入口                      │
                    │  FeatureDevelopmentAgent.run()            │
                    └──────────────────┬───────────────────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────┐
        │                              │                          │
   ┌────▼──────────────┐    ┌──────────▼──────────┐   ┌─────────▼──────────┐
   │   通道1: 模板召回  │    │  通道2: LLM推理新模板 │   │通道3: 用户知识→模板 │
   │   确定性参数展开   │    │  需人工确认晋升      │   │知识提取→审核→晋升  │
   │   DSL→Python代码  │    │  skill_channel2_    │   │knowledge_extractor  │
   │   (90%特征)       │    │  reasoning()        │   │template_generation  │
   └────────┬─────────┘    └──────────┬──────────┘   └─────────┬──────────┘
            │                         │                        │
            └──────────────┬──────────┴───────────┐────────────┘
                           │                      │
                    ┌──────▼──────┐       ┌───────▼───────┐
                    │ 写入最终代码 │       │ channel2_    │
                    │             │       │ pending.json │
                    │             │       │ → 前端审核   │
                    └─────────────┘       │ → 晋升通道1  │
                                          └───────────────┘
```

### 5.2 通道1 — 冷启动DSL模板（主力路径，确定性代码）

这是系统的核心路径，**绕过LLM**，直接用确定性代码生成特征。

**流程**:
1. **模板召回** (`skill_template_recall`): 根据维度名从 `channel1_templates.json` 匹配模板
2. **参数填充** (`skill_param_fill`): `_generate_param_combinations()` 枚举所有有效参数组合
3. **DSL→Python** (`skill_dsl_to_python`): 加载 `channel1_calculators.py` 对应函数生成调用代码

**Mass Producer引擎** (`feature_mass_producer.py`):
- `_build_param_combos()`: 定义所有模板的参数组合枚举逻辑
- `produce_all_features()`: 生成完整FeatureCalculator类(418主特征+124衍生)
- `_validate_t016_references()`: 校验T016衍生特征引用的主特征是否存在

### 5.3 通道2 — LLM推理新模板（创新路径）

当通道1无匹配时触发。

**触发条件**: `risk_gap`参数描述了通道1无法覆盖的风险模式

**晋升机制** (`promote_template()`):
```
通道2推理结果 → 校验完整性 → AUTO_PROMOTE=true? → 是 → 写入channel1_templates.json
                           → 否 → 写入channel2_pending.json → 前端Template页审核
```

**关键配置**:
- 环境变量 `AUTO_PROMOTE_TEMPLATE=true/false`（默认false，需人工确认）

### 5.4 通道3 — 用户知识驱动（知识驱动路径）

**流程**:
```
用户上传知识文档(PDF/Word/Excel)
  → knowledge_extractor.py 提取结构化知识
    → template_generation_agent.py 生成模板
      → 写入channel2_pending.json
        → 前端Template Sidebar审核 → 确认后晋升到通道1
```

**关键文件**:
- `backend/services/knowledge_extractor.py`: 提取服务
- `agents/template_generation_agent.py`: 模板生成Agent


---

## 六、Skills 框架设计背景

### 6.1 为什么要引入Skill抽象层？

系统从v1(6Agent串行)演进到v3的过程中，遇到了三个核心问题：

**问题1: LLM调用的不确定性**
- 同样的特征需求，每次LLM生成不同参数组合
- bug修复困难，"这次跑出来和上次不一样"
- 无法做回归测试

**问题2: 质量无法保证**
- LLM生成的代码可能漏掉防穿越检查
- DSL语法错误需要反复重试
- 没有机制在生成时即时拦截不合格输出

**问题3: Agent职责边界模糊**
- 特征设计Agent和特征工程Agent之间大量重复代码
- 数据传递靠文件，版本混乱
- 审核不通过要"绕一大圈"才能修正

**解决方案**: 将Agent拆分为"控制流" + "原子Skill"，每个Skill自带质量门。

### 6.2 Skill框架结构

```
Agent 控制流层 (FeatureDevelopmentAgent.run())
  │
  ├─ 调用 skill_xxx() → SkillRegistry.execute("xxx", **kwargs)
  │    │
  │    ├─ 最多重试3次
  │    │    ├─ 1. 执行 Skill 函数
  │    │    ├─ 2. 执行 post_hook 校验列表
  │    │    ├─ 3. 全部通过 → 返回 SkillResult(success=True, data)
  │    │    └─ 4. 有失败 → 重试 (LLM Skill可带hook_feedback自修正)
  │    │
  │    └─ 返回 SkillResult(success/fail + data + error + hook_errors)
  │
  └─ 根据结果决定下一步流程
```

### 6.3 已注册的Skill及其质量门

| Skill | 实现方式 | post_hook校验 | 可重试 |
|-------|---------|---------------|--------|
| template_recall | 代码(从JSON匹配) | — | — |
| param_fill | 代码(确定性枚举) | — | — |
| dsl_to_python | 代码(调用channel1函数) | compile_check, anti_travel_check, dsl_syntax_check | 是 |
| channel2_reasoning | LLM | — | 是 |
| self_review | LLM | — | 是 |

**内置post_hook check函数**(`skill_registry.py`):
- `check_python_compile()`: Python代码能否通过`ast.parse()`编译
- `check_anti_time_travel()`: 是否使用 `datetime.now()` → **防穿越红线**
- `check_dsl_syntax()`: DSL表达式是否符合定义的模式
- `check_param_completeness()`: 参数是否包含所有必需字段

### 6.4 Skill的设计原则

```
1. 确定性优先: 能用代码实现的Skill绝不用LLM
   ✅ skill_template_recall / skill_param_fill / skill_dsl_to_python
   ❌ 旧版: 全部走LLM生成

2. 质量门前置: 校验在生成时即时拦截，不留给下游
   ✅ dsl_to_python执行完立即检查编译+防穿越
   ❌ 旧版: 等审核Agent发现问题再打回重做

3. LLM只做"创意": 只有需要业务理解的地方才调LLM
   ✅ channel2_reasoning(新模板设计)、self_review(整体审视)
   ❌ 旧版: 参数选择、代码生成也调LLM

4. Skill可插拔: 替换实现不影响Agent控制流
   ✅ 参数设计从LLM版替换为确定性版，接口不变Agent代码无需修改
```


---

## 七、特征评估体系

### 7.1 评估指标与门槛

| 指标 | 门槛 | 含义 | 计算方式 |
|------|------|------|---------|
| **IV** (Information Value) | >= 0.02 | 特征区分好坏客户的能力 | `sum((bad_i/total_bad - good_i/total_good) * WOE_i)` |
| **PSI** (Population Stability Index) | <= 0.25 | 特征在训练集和OOT之间的分布稳定性 | `sum((P_train_i - P_oot_i) * ln(P_train_i/P_oot_i))` |
| **非缺失覆盖率** | > 5% | 特征值的可用比例 | `非空样本数 / 总样本数` |

### 7.2 两轮评估流程

```
Pass 1: 参考分布预计算
  训练集(80%) → 计算所有特征 → 提取T010-T012参考分布
  (salary_distribution, loan_amount_distribution, inquiry_count_distribution, applist_count_distribution)
  ↓
Mass Produce: 注入参考分布，生成最终特征代码
  produce_all_features(ref_distributions=refs) → features_calculator_v2.py
  ↓
Pass 2: 全量评估
  加载最终计算器 → 全量样本计算特征 → 逐特征计算IV/PSI/覆盖率 → 筛选
  ↓
输出: HTML评估报告 + CSV + iv_psi_feedback_rN.json
```

### 7.3 数据划分策略

```python
# Time-based split (推荐)
oot_ratio = 0.2
按 apply_time 降序排列 → 最新的20%作为OOT

# Fallback: random split
np.random.seed(42) → 随机80/20划分
```

### 7.4 IV/PSI反馈回路

每轮评估结果写入 `outputs/evaluation/iv_psi_feedback_r{N}.json`:

```json
{
  "round": 1,
  "template_feedback": [
    {
      "template_id": "T001",
      "channel": "channel1",
      "passed": {"count": 12, "avg_iv": 0.15, "avg_psi": 0.08},
      "failed": {"count": 3, "reasons": [...]}
    }
  ],
  "summary_patterns": ["窗口较长的count特征IV更高"]
}
```

下一轮特征开发时自动加载最近3轮反馈，LLM据此调整设计策略。

---

## 八、模板与特征设计的关系

### 8.1 核心设计哲学：三阶段风险驱动

```
数据维度                 风险模式                 特征产出
──────────              ────────                ────────
APP安装行为     →  多头借贷 / 高风险偏好   →  T001-T009 (计数+占比+集中度等)
FDC征信记录     →  共债风险 / 欺诈信号     →  T001-T009 (查询频次+机构分散度等)
借贷历史+申报   →  收入不稳定 / 信息造假   →  T010-T015 (百分位+跨源不一致等)
                                                    + T016 (衍生变换)
```

### 8.2 模板 = 计算骨架，参数 = 业务血肉

```
模板(T001 count): "统计N天内某类事件的数量"
  └─ 参数1: source="fdc_inquiry", window=30 → "近30天征信查询次数"
  └─ 参数2: source="applist", window=7, category="gambling" → "近7天赌博APP安装数"

模板(T005 concentration): "计算某字段的集中度"
  └─ 参数1: method="gini", category_field="id_penyelenggara", window=90 → "贷款机构Gini集中度"
```

**Mass Producer** 枚举所有 `(模板 × 数据源 × 窗口 × 过滤条件)` 组合 → 418主特征 + T016衍生124 = **542个特征**

### 8.3 特征命名规范

```
格式: {prefix}_{template_abbr}_{source}_{cond}_{window}d

示例:
  cnt_fdc_inquiry_30d          → count, FDC查询, 30天
  dcnt_fdc_pinjaman_idorg_90d  → distinct_count, 贷款机构去重, 90天
  prop_applist_gambling_30d    → proportion, APP赌博类占比, 30天

T016衍生特征(加d_前缀):
  d_ratio_cnt_inquiry_30d_vs_cnt_applist_30d  → 比值
  d_speed_cnt_fdc_inquiry_30d                 → 日增速
```

### 8.4 16个DSL模板一览

| ID | 名称 | 维度 | 组合数 | 说明 |
|----|------|------|--------|------|
| T001 | count | 全部 | 97 | 时间窗口计数 |
| T002 | distinct_count | FDC/借贷 | 29 | 去重计数 |
| T003 | decayed_sum | 借贷 | 48 | 衰减求和(nilai_pendanaan) |
| T004 | proportion | APP/FDC | 107 | 高风险占比 |
| T005 | concentration | APP/FDC | 44 | 集中度(Gini/熵/CV/HHI) |
| T006 | overlap | APP+FDC | 4 | 重叠度 |
| T007 | period_compare | 全部 | 24 | 短/长窗口对比 |
| T008 | trend | 全部 | 14 | 多窗口趋势斜率 |
| T009 | spike | APP/FDC | 24 | 突增检测 |
| T010 | percentile | 全局分布 | 4 | 百分位排名 |
| T011 | deviation | 全局分布 | 4 | Z-Score偏差 |
| T012 | anomaly | APP/借贷 | 2 | 异常检测 |
| T013 | declared_vs_actual | 申报 | 6 | 申报vs实际偏差 |
| T014 | cross_discrepancy | 跨源 | 1 | 跨源不一致 |
| T015 | identity_cluster | APP/FDC | 2 | 团伙聚类 |
| T016 | derived | 全部 | 124 | 衍生变换(比值/密度/速度等) |


---

## 九、部署与交付

### 9.1 部署包结构 (v9)

```
outputs/deployment/v9/
├── api/app.py                 FastAPI服务(鉴权+超时+标准返回格式)
├── core/feature_calculator.py 特征计算核心(含所有542个特征)
├── config/version.json        版本信息(feature总数等)
├── deploy/
│   ├── Dockerfile             Docker构建文件
│   ├── docker-compose.yml     Docker编排(2G内存限制)
│   └── deploy.sh              一键部署脚本
├── docs/                      API文档
├── examples/                  调用示例
├── requirements.txt           Python依赖
└── .gitignore
```

### 9.2 API接口

**单样本计算**:
```
POST /api/v1/calculate
Headers: X-API-Key: <your_api_key>
Body: {
  "order_id": "id002xxx",
  "raw_data": { ... },       // 订单完整JSON
  "apply_time": "2026-03-09" // 可选，默认从orderId提取
}
```

**标准化返回格式**:
```json
// 成功
{"status": "success", "version": "v9", "order_id": "...", 
 "processing_time_ms": 1234, "features": {...}}

// 超时(1.8s)
{"status": "timeout", "message": "计算超过服务端超时限制(1800ms)...", "features": {}}

// 错误
{"status": "error", "message": "内部计算错误: ...", "features": {}}
```

**批处理**:
```
POST /api/v1/calculate_batch  → {"job_id": "batch_...", "total": N}
GET  /api/v1/batch_status/{job_id}  → 轮询进度
GET  /api/v1/batch_results/{job_id} → 获取结果
```

### 9.3 部署架构

| 项目 | 配置 |
|------|------|
| 服务器 | 阿里云硅谷轻量云 (2C 8G) |
| 服务方式 | Docker单容器 |
| 端口 | 8000 |
| 鉴权 | X-API-Key Header (环境变量 FEATURE_API_KEY) |
| 超时 | 1.8s (环境变量 CALCULATE_TIMEOUT) |
| 内存 | 限制2G / 预留512M |
| 防火墙 | 22端口(SSH) + 8000端口(API) |

### 9.4 一键部署

```bash
# 服务器上执行
cd /opt/riskfeature-api/deploy
docker-compose up -d --build
```

或使用部署脚本:
```bash
bash deploy/deploy.sh
```

---

## 十、关键技术债务与优化方向

| 序号 | 问题 | 说明 | 建议 |
|------|------|------|------|
| 1 | **性能** | 542个特征计算 ~2s，可能不满足高并发 | 优化热路径、引入特征缓存、考虑异步预计算 |
| 2 | **并发** | 单容器单进程，ThreadPoolExecutor max_workers=4 | 生产环境配置多Docker容器+负载均衡 |
| 3 | **数据库** | SQLite不支并发写，生产环境不可用 | 迁移到 PostgreSQL |
| 4 | **特征解释性** | 特征命名对业务人员不够友好 | 维护特征名↔中文描述映射表 |
| 5 | **APP分类维护** | 规则引擎手工维护成本高 | 定期用LLM自动更新规则库 |
| 6 | **监控告警** | 无服务监控、无调用统计 | 接入Prometheus + Grafana |
| 7 | **测试覆盖** | 后端单测12KB，前端基本无单测 | 增加单元测试和集成测试 |
| 8 | **CI/CD** | 无自动化流水线 | 配置GitHub Actions自动构建+部署 |

---

## 十一、快速启动指南

### 11.1 本地开发环境

```bash
# 1. 后端
cd backend
pip install -r requirements.txt
uvicorn backend.app.main:app --reload --port 8000

# 2. 前端
cd web-frontend
npm install
npm run dev

# 3. 运行特征挖掘流水线
python agents/feature_orchestrator.py --mode full
# 或从指定步骤继续
python agents/feature_orchestrator.py --start-from feature_evaluation
```

### 11.2 关键配置文件

| 文件 | 作用 |
|------|------|
| `.env` | OpenRouter API Key + 其他环境变量 |
| `configs/model_config.yaml` | LLM模型配置(当前: qwen3.6-plus) |
| `backend/app/config.py` | 后端配置(Settings类) |

### 11.3 常用命令

```bash
# 重新生成特征计算器(不跑评估)
python -c "from agents.feature_mass_producer import produce_all_features; code=produce_all_features(); open('outputs/feature_code/features_calculator_v2.py','w').write(code)"

# 查看IV/PSI反馈
cat outputs/evaluation/iv_psi_feedback_r1.json | python -m json.tool

# 重新打包部署
python agents/feature_deployment_agent.py

# 前端类型检查
cd web-frontend && npx tsc --noEmit

# 前端构建
cd web-frontend && npx vite build
```

### 11.4 必读文档

| 文档 | 说明 |
|------|------|
| `CLAUDE.md` | 项目整体规范和架构(28KB) |
| `DEV_PLAN.md` | 开发计划和进度(16KB) |
| `LESSONS_LEARNED.md` | 踩坑记录(48KB, **推荐通读**) |
| `AGENT_ORCHESTRATOR_LESSONS.md` | 主Agent流程指南(10KB) |
| `WEB_ARCHITECTURE.md` | Web架构设计(31KB) |

---

> **本文件结束** — 如有疑问请联系AI原型开发团队。
