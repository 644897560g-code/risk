# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ 重要：开发规范

**请严格遵循 `DEV_PLAN.md` 进行开发！**

- 📋 **开发计划**: 查看 `DEV_PLAN.md` 了解整体开发进度和当前任务
- 🔄 **状态更新**: 每完成一个模块，必须立即更新 `DEV_PLAN.md` 中对应的任务状态（将 `[ ]` 改为 `[x]`，状态改为 `✅ 已完成`）
- 📝 **记录交付物**: 完成后在 `DEV_PLAN.md` 中记录实际交付的文件路径
- 🚀 **断点续做**: 用户重启对话后，Claude Code会读取 `DEV_PLAN.md` 了解下一步要做什么
- ⚠️ **避免踩坑**: 阅读 `LESSONS_LEARNED.md` 了解已踩过的坑和关键设计原则
- 📖 **主Agent流程指南**: `AGENT_ORCHESTRATOR_LESSONS.md` - 主Agent专用知识库（重启后必读！）
- 📝 **知识积累**: **遇到重要问题时，必须立即更新 `LESSONS_LEARNED.md`**（详见下方"知识更新流程"）

## 📖 必读文档（重启后必读）

每次重启Claude Code后，请按顺序阅读以下4个文档快速恢复上下文：

1. **CLAUDE.md** - 项目整体说明和架构设计（本文档）
2. **DEV_PLAN.md** - 当前开发进度和下一步任务
3. **AGENT_ORCHESTRATOR_LESSONS.md** - 🤖 主Agent专用流程指南（新！）
4. **LESSONS_LEARNED.md** - ⚠️ 已踩过的坑和关键教训

## 📝 知识更新流程（重要）

**何时更新 LESSONS_LEARNED.md**：

当你遇到以下情况时，必须立即更新 `LESSONS_LEARNED.md`：

1. **用户纠正你的错误** - 如"不要这样做"、"你搞错了"、"应该..."
2. **API调用失败或成本过高** - 如超出token限制、返回错误
3. **关键设计决策** - 如选择某种架构方案的原因
4. **性能优化经验** - 如发现某个操作特别慢或有更优方案
5. **Bug修复** - 特别是容易被重复踩的坑

**如何更新**：

在 `LESSONS_LEARNED.md` 末尾添加新条目，包含以下结构：

```markdown
## YYYY-MM-DD: [问题简述]

### 问题描述
[用户反馈或问题现象]

### 解决方案
[具体解决办法和代码示例]

### 验证结果
[实际测试数据证明修复有效]

### 设计原则
[可以复用的经验教训]

### 影响范围
- 修改文件: xxx.py
- 修改方法: yyy()
- 相关文档: zzz.md
```

**为什么重要**：

- 📖 **知识传承**: 避免重复踩同样的坑
- 🚀 **效率提升**: 下次遇到类似问题直接查阅解决方案
- 💡 **质量保证**: 积累的经验能帮助做出更好的设计决策
- 🎯 **团队协作**: 其他开发者也能从这些经验中受益

**示例参考**：

参见 `2026-04-25: LLM调用不能发送原始数据` 条目的完整格式。

## 项目目标

开发一个面向**印尼市场短期现金贷业务**的风险特征挖掘Agent系统，包含六个核心Agent：

1. **数据分析Agent** - 分析客户申请信息（base信息、applist、FDC数据）和贷后好坏表现，形成业务专有领域知识
2. **特征设计Agent** - 基于数据分析结果、印尼现金贷常识和FDC特征变量清单，设计新增特征指标（去重、包含特征名、业务解释、设计理由）
3. **特征工程Agent** - 根据特征设计结果开发特征计算代码
4. **特征工程审核Agent** - 审核特征代码语法合法性和逻辑正确性，不通过则返回修正直到通过
5. **特征评估Agent** - 划分包含OOT的数据集，计算IV、PSI、非缺失覆盖率，筛选IV>=0.02、PSI<=0.25、覆盖率>5%的特征，输出HTML报告
6. **特征部署Agent** - 将保留的特征代码打包供风控团队部署到线上

## 项目文件说明

### 数据文件
- **0421全样本短链.txt** (2915行) - 每个订单申请时的数据链接URL，可通过短链直接加载JSON数据
- **印尼模型分_2026_04_21_建模样本aiagent.xlsx** (2272行×5列) - 订单好坏表现标签
  - 列: loan_date, repay_date, source, source_order_no, is_overdue
  - 逾期率: 72.45% (标签1为逾期，0为正常)
  - 来源: FlexRupiah (2156条), TemanPinjam (116条)
  - **聚焦首贷客户**：特征挖掘针对首次贷款客户，避免首贷和复贷数据混合影响特征效果
- **FDC4710变量.xlsx** (4710行×2列) - 风控团队提供的历史FDC特征变量名清单
  - 版本: v8 (4641个), v9 (69个)
  - 变量类型: dpd(1493), cnt(1235), amt(858), ratio(2451), avg(245), max(289), overdue(958)等
- **id002luzt202603090951432723072** - 单个订单申请样例JSON文件
  - 包含: base基础信息、applist应用列表、FDC信用报告、特征变量(122维)、风险评分
- **智能纪要：特征挖掘 ai助手对接沟通 2026年4月23日.pdf** - 与风控团队会议纪要

### 数据样例结构 (id002luzt202603090951432723072)
```json
{
  "country": "INDO",
  "orderId": "id002luzt202603090951432723072",
  "params": {
    "base": {
      "appname": "flex-rupiah",
      "birthday": "15-02-1973",
      "job": "12",
      "gender": 0,
      "salary": 12000000,
      "workYears": 4,
      "marita": 1,
      "children": 0
    },
    "appList": [47个应用的安装信息],
    "smsList": [],
    "Indo_XD_score": 381.888,
    "feature": {
      "feature_1": 1,
      ...
      "feature_122": 18
    }
  },
  "FDC": {
    "history_inquiry": { /* 信用查询历史 */ },
    "pinjaman": [23笔贷款记录],
    "platform_aktif": { /* 活跃平台4个 */ }
  }
}
```

## Agent模型配置

每个Agent都是独立的LLM模型实例，统一使用 **qwen3.6-plus** 作为底层模型：

| Agent | 模型 | 职责 |
|-------|------|------|
| 数据分析Agent | qwen3.6-plus | 分析base/applist/FDC数据，形成业务知识库 |
| 特征设计Agent | qwen3.6-plus | 基于业务知识和FDC清单设计新增特征 |
| 特征工程Agent | qwen3.6-plus | 开发特征计算代码 |
| 特征工程审核Agent | qwen3.6-plus | 审核代码语法和逻辑，循环修正 |
| 特征评估Agent | qwen3.6-plus | 计算IV/PSI/覆盖率，输出HTML报告 |
| 特征部署Agent | qwen3.6-plus | 打包特征代码供线上部署 |

## 系统架构设计

### 六Agent协作流程

```
┌─────────────────────────────────────────────────────────┐
│                    数据准备层                              │
│  短链文件 → 订单申请JSON → 好坏标签 + FDC变量清单          │
└────────────────────┬──────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              数据分析Agent (Agent 1)                       │
│  输入: base信息, applist, FDC, 好坏标签                    │
│  输出: 业务专有领域知识结构、统计特征                       │
│  任务:                                                    │
│  - 分析申请信息与逾期表现的相关性                          │
│  - 分析应用安装列表的风险信号                              │
│  - 分析FDC信用报告的模式                                  │
│  - 形成结构化业务知识库                                    │
└────────────────────┬──────────────────────────────────────┘
                     │ 结构化业务知识
                     ▼
┌─────────────────────────────────────────────────────────┐
│              特征设计Agent (Agent 2)                       │
│  输入: 业务知识库 + FDC4710变量清单 + 印尼现金贷常识        │
│  输出: 特征设计文档（特征名、业务解释、设计理由）           │
│  任务:                                                    │
│  - 设计新增特征指标（不与现有4710个FDC特征重复）            │
│  - 特征业务解释                                            │
│  - 说明设计理由                                            │
└────────────────────┬──────────────────────────────────────┘
                     │ 特征设计文档
                     ▼
┌─────────────────────────────────────────────────────────┐
│             特征工程Agent (Agent 3)                        │
│  输入: 特征设计文档                                        │
│  输出: 特征计算代码                                        │
│  任务: 根据特征定义开发可执行的计算代码                     │
└────────────────────┬──────────────────────────────────────┘
                     │ 特征代码
                     ▼
┌─────────────────────────────────────────────────────────┐
│           特征工程审核Agent (Agent 4)                      │
│  输入: 特征代码                                            │
│  输出: 审核结果（通过/不通过+修正建议）                     │
│  任务:                                                    │
│  - 审核语法合法性                                          │
│  - 审核逻辑正确性                                          │
│  - 不通过则返回Agent 3修正，循环直至通过                   │
└────────────────────┬──────────────────────────────────────┘
                     │ 审核通过的特征代码
                     ▼
┌─────────────────────────────────────────────────────────┐
│              特征评估Agent (Agent 5)                       │
│  输入: 审核通过的特征代码 + 样本数据                        │
│  输出: 筛选后的特征集合 + HTML评估报告                      │
│  任务:                                                    │
│  - 划分训练集和OOT数据集                                   │
│  - 计算每个特征的IV值（>=0.02通过）                        │
│  - 计算PSI稳定性（<=0.25通过）                             │
│  - 计算非缺失覆盖率（>5%通过）                             │
│  - 输出HTML评估报告                                        │
└────────────────────┬──────────────────────────────────────┘
                     │ 筛选后的特征代码
                     ▼
┌─────────────────────────────────────────────────────────┐
│             特征部署Agent (Agent 6)                        │
│  输入: 筛选后的特征代码                                    │
│  输出: 打包的特征计算包                                    │
│  任务: 将特征代码打包供风控团队部署到线上                   │
└─────────────────────────────────────────────────────────┘
```

### 新架构：FeatureOrchestrator 主Agent协调（2026-05-04更新）

```
┌─────────────────────────────────────────────────────────┐
│           FeatureOrchestrator (主协调Agent)                │
│  职责:                                                    │
│  - 统一协调完整流程：数据分析→设计→工程→审核→评估          │
│  - 管理Agent间数据传递 + 数据流注册表                      │
│  - 处理流程中断和断点续做                                  │
│  - 审核不通过时自动打回特征工程（最多3次重试）              │
│  - 记录执行状态到 orchestrator_state.json                  │
│  - 记录数据流到 data_flow_registry.json                    │
│                                                          │
│  使用方式:                                                │
│  python agents/feature_orchestrator.py                   │
│  python agents/feature_orchestrator.py --start-from xxx  │
```

#### 数据流注册表（Data Flow Registry）

主Agent通过 `DataFlowRegistry` 类管理Agent之间的文件依赖关系：

```python
# 每次Agent执行后自动注册
data_flow.register_execution(
    agent_name='feature_engineering',
    inputs={'feature_design_doc': '...'},
    outputs={'features_calculator': '...'},
    metadata={'status': 'completed'}
)

# 下一个Agent自动从注册表获取输入
code_file = data_flow.get_latest_output('features_calculator')
```

**优势**:
- 完整的执行历史追踪（谁→用了什么→产出什么）
- 版本管理（审核重试时区分不同版本）
- 断点续做（根据历史记录恢复正确的文件依赖）

**相关文件**:
- `outputs/feature_code/orchestrator_state.json` - 流程状态
- `outputs/feature_code/data_flow_registry.json` - 数据流注册表
- `outputs/feature_code/DATA_FLOW_REGISTRY.md` - 详细文档
└──────────────┬──────────────┬──────────────┬─────────────┘
               │              │              │
    ┌──────────▼─────┐ ┌─────▼──────┐ ┌────▼──────────┐
    │ 特征设计Agent  │ │特征工程Agent│ │特征审核Agent  │
    │ (按需调用)      │ │(含自主修复) │ │(+人工确认)    │
    └────────────────┘ └────────────┘ └───────────────┘
```

**关键特性**:
- **断点续做**: `--start-from feature_review` 从指定步骤继续
- **循环重试**: 审核不通过自动打回特征工程，附带审核反馈
- **自主修复**: 特征工程Agent读取审核反馈JSON，LLM理解问题并自主修复
- **人工确认**: 审核通过后需要人工输入 `yes` 确认
- **状态持久化**: 所有进度保存到 `outputs/feature_code/orchestrator_state.json`

---

## 已完成的

### ✅ 应用分类模块（2026-04-26完成）

**批量分类任务执行情况**:
- 完整应用清单：11,851个应用（2,147好客户 + 6,892坏客户 + 2,812共有）
- LLM分批分类：60批次，每批200个应用
- 成功分类：11,850个应用（99.99%成功率）
- 总耗时：459.5分钟（约7.7小时）
- 15个标准类别体系 + 类别优先级规则

**输出文件**:
```
outputs/app_analysis/classification_complete_11850.json  - 完整分类结果（1.6MB）
outputs/app_analysis/classification_statistics.json      - 类别统计
outputs/app_analysis/app_classification_complete.csv     - 应用清单（11,847行）
outputs/app_analysis/category_rules.json                 - 规则库
outputs/app_analysis/category_rules_summary.md           - 规则摘要
```

**高风险类别识别结果**:
| 类别 | 数量 | 占比 | 说明 |
|------|------|------|------|
| gambling | 561 | 4.7% | 赌博/棋牌/老虎机 |
| cash_loan | 262 | 2.2% | 现金贷应用 |
| fintech_lending | 116 | 1.0% | 金融科技借贷 |
| fake_gps | 29 | 0.2% | 虚拟定位工具 |
| clone_app | 28 | 0.2% | 应用克隆工具 |
| app_store | 26 | 0.2% | 第三方应用商店 |

**关键经验教训**:
- LLM调用应发送统计摘要而非原始数据（Token优化98%）
- 批处理策略：每批200个应用，带重试机制
- 类别优先级规则：高风险 > 金融 > 通用 > 兜底
- 规则库可用于自动化分类，减少LLM依赖

## 关键业务规则（来自会议纪要）

### 1. 防穿越机制（重要）
- **核心原则**：特征计算只能使用用户申请时间之前的信息，不能使用申请之后的数据
- **实施要求**：在特征工程中必须加入防穿越机制，确保特征的时间正确性
- **时间计算标准**：如根据RFM原则计算近3天、近7天数据，要从用户申请时间往前推，而非当前程序运行时间

### 2. 特征审核机制
- **审核方式**：风控团队提供2000样本，系统返回特征值，进行IV和PSI验证
- **审核重点**：关注产出的特征质量，通过离线接口拉取数据测试，加入已有策略或模型看提升效果
- **评审流程**：新开发特征上线前需评审

### 3. 数据交付方式
- **输入数据**：
  - 短链地址（每个订单申请JSON的URL）
  - FDC现有特征清单
  - 订单号与好坏标签数据
- **输出交付**：
  - 挖掘出的特征以JSON串形式返回样本特征值
  - 打包黑盒供本地化部署，保证服务稳定

### 4. 数据结构说明
- **风控推入数据**：单号、策略线编号、订单进件时间、产品号、基础信息（设备号、银行卡号、身份证号等）、APP list数据和FDC信息
- **APP list数据**：包含用户安装APP的信息（安装时间、更新时间、名称、类型、版本、包名等），只抓用户自装应用
- **FDC信息**：基于印尼OJK（金融服务管理局）互联网金融协会的三方信用机构查询统计数据
  - 历史查询统计
  - 近三天查询机构及时间
  - 用户信贷记录（每条以JSON串形式呈现）
  - 注意：部分机构（如银行）不上传数据，存在覆盖率问题

### 5. 测试时间线
- 数据给到后**两周内**进行测试并给出结果
- 先针对**首贷客户**进行特征挖掘

---

## 📱 离线批量APP分类 vs 特征工程主Agent（重要架构说明）

### 职责边界

| 维度 | 离线APP分类任务 | 特征工程主Agent |
|------|----------------|----------------|
| **执行频率** | 每天凌晨批量执行 | 按需执行（特征开发/迭代时） |
| **触发方式** | 定时调度（cron/launchd） | 用户主动触发 |
| **任务性质** | 数据预处理/基础设施维护 | 特征挖掘业务流程 |
| **数据流向** | 原始数据 → 分类缓存 | 分类缓存 → 特征代码 |
| **耦合度** | 独立运行 | 只读依赖分类结果 |

### 正确的架构关系

```
离线APP分类任务（独立，定时执行）
│
├─ 定时执行: 每天凌晨2点
├─ 输入: 新增的unknown APP
├─ 输出: 更新 classification_complete_XXXXX.json
└─ 不依赖特征工程流程

特征工程主Agent（按需执行）
│
├─ 用户触发: python agents/feature_orchestrator.py
├─ 读取: 最新的分类缓存（自动检测最新文件）
├─ 输出: 特征代码 + 审核报告
└─ 依赖分类结果（只读，不修改）
```

### 为什么应该分开？

1. **执行周期不同**: APP分类每日固定执行，特征工程按需执行
2. **失败影响不同**: APP分类失败不影响已有特征，特征工程失败直接影响模型
3. **监控告警不同**: 两者的SLI/SLO指标完全不同
4. **权限和安全**: APP分类涉及LLM API成本，特征工程涉及风控数据隐私

### 关键实现细节

**特征计算器自动读取最新分类缓存**:
```python
# features_calculator_v2.py
def _load_app_cache(self) -> Dict:
    """动态加载最新的分类缓存文件"""
    cache_dir = 'outputs/app_analysis'
    # 查找最新的 classification_complete_*.json 文件
    cache_files = [f for f in os.listdir(cache_dir)
                   if f.startswith('classification_complete_') and f.endswith('.json')]
    latest_cache = max(cache_files,
                      key=lambda f: os.path.getmtime(os.path.join(cache_dir, f)))
    # 自动使用最新文件
```

这样设计的好处：
- 离线分类任务每天产出新文件，无需修改任何代码
- 特征工程下次执行时自动读取最新结果
- 两个系统完全解耦，通过文件系统传递数据

---

## 📱 在线APP分类流程（重要）

### 架构设计

在线APP分类采用**两级分类 + 夜间批量补充**的架构：

```
用户申请 → 提取APP列表
  ↓
第一级：缓存查询（已知APP）
  ├─ 匹配 classification_complete_11850.json (11,850个历史样本)
  └─ 返回类别 + 置信度
  ↓
未命中 → 第二级：规则引擎分类
  ├─ 加载 online_app_classification_rules_llm.json (LLM生成的规则库)
  ├─ 多维度评分（关键词 + 正则 + 品牌）
  └─ 返回类别 + 置信度 + 判定依据
  ↓
仍无法判定 → 标记为 unknown
  └─ 等待夜间批量LLM分类
```

### 核心组件

| 组件 | 文件路径 | 功能 |
|------|---------|------|
| **规则引擎分类器** | `data/rule_engine_classifier.py` | 两级分类流程 |
| **LLM规则库** | `outputs/risk_rules/online_app_classification_rules_llm.json` | 16个类别的判定规则 |
| **分类缓存** | `outputs/app_analysis/classification_complete_11850.json` | 11,850个已知APP |
| **夜间批处理** | `data/batch_classify_new_apps.py` | 批量分类unknown APP |
| **定时任务** | `scripts/run_batch_classification.sh` | 每天凌晨2点执行 |

### 使用方式

**Python调用**：
```python
from data.rule_engine_classifier import RuleEngineClassifier

classifier = RuleEngineClassifier()
result = classifier.classify('com.newapp.package')
# 返回: {category, confidence, reason, method}
```

**API输出格式**：
```json
{
  "package_name": "com.id5dan777.ntla337",
  "category": "gambling",
  "confidence": 0.95,
  "reason": "正则匹配: NTLA白牌模板特征",
  "method": "rule_engine"
}
```

### 规则库结构

LLM生成的规则库包含16个类别（排除other兜底类别）：

**高风险类别**（6个）：
- gambling（赌博）、cash_loan（现金贷）、fintech_lending（金融科技借贷）
- fake_gps（虚拟定位）、clone_app（应用克隆）、app_store（第三方商店）

**其他类别**（10个）：
- banking、ewallet、shopping、transportation、food_delivery
- productivity、utility、religious、social_entertainment、installment

每个类别包含：
- `keywords` - 印尼语/英语特征词
- `patterns` - 正则表达式（带中文描述）
- `brands` - 品牌白名单
- `exclusion_rules` - 排除规则

### 夜间批量分类流程

**定时任务**：每天凌晨2点执行
1. 扫描 `data/unknown_apps.json`（新增的unknown APP）
2. 批量调用LLM分类（与历史11,850个相同的Prompt）
3. 结果回写 `classification_cache.json`
4. 生成报告到 `outputs/app_analysis/batch_classification_YYYYMMDD.md`

**配置定时任务**：
```bash
# macOS (launchd)
launchctl load ~/Library/LaunchAgents/com.riskagent.batchclassify.plist

# 手动执行
python data/batch_classify_new_apps.py --input data/unknown_apps.json
```

---

## 开发指导原则

### 技术要求
- **语言**: Python（推荐用于数据分析和特征工程）
- **数据处理**: pandas, numpy
- **特征评估**: 需要计算IV、PSI等传统风控指标
- **报告生成**: HTML格式评估报告
- **服务稳定性**: 特征计算服务需要保证稳定性，支持线上接口调用

### 关键约束
1. **特征去重**: 新增特征不能与FDC4710变量清单中的4710个特征重复
2. **质量门槛**: IV>=0.02且PSI<=0.25且覆盖率>5%
3. **审核循环**: 特征工程审核不通过必须返回重新开发
4. **部署导向**: 最终产出是可打包部署的特征计算包（黑盒形式）
5. **防穿越约束**: 特征计算只能用申请时间之前的数据
6. **Web开发**: 系统采用前后端分离架构，6周完成Web应用（详见 `WEB_DEV_PLAN.md`）

### 数据理解要点
- **FDC数据**: 印尼MDK户均协会提供的三方征信数据，包含历史查询、近三天查询和用户信贷记录
- **applist**: 用户手机安装的应用列表，是特征主要来源，包含安装时间、更新时间、名称、类型、版本、包名等
- **好坏标签**: is_overdue=1表示逾期，is_overdue=0表示正常
- **特征变量**: 现有122维基础特征（feature_1到feature_122）
- **首贷客户**: 特征挖掘聚焦首次贷款客户，避免首贷和复贷混合

## 常见任务

1. **数据探索**: 了解数据分布、相关性、风险信号
2. **特征设计**: 基于业务理解设计新的风控特征（重点关注applist、FDC、统计数据）
3. **特征开发**: 编写特征计算代码（注意防穿越机制）
4. **特征评估**: 计算IV/PSI等指标筛选特征
5. **报告生成**: 输出特征评估HTML报告
6. **打包部署**: 准备生产环境部署包（黑盒形式）

## ⚠️ 关键设计原则（来自踩坑经验）

### LLM调用原则

**核心教训**: 发送统计摘要而非原始数据

- ✅ **DO**: 使用pre-computed aggregated statistics
- ❌ **DON'T**: 发送原始JSON或大量逐条记录
- 💡 **Why**: Token成本降低99.6%，保护隐私，提高可扩展性

详见: `LESSONS_LEARNED.md`

## Web开发任务

- **后端**: FastAPI + Celery + SQLite + Redis
- **前端**: React 18 + TypeScript + Ant Design + ECharts
- **API文档**: 见 `WEB_ARCHITECTURE.md` 中的接口设计
- **开发计划**: 见 `WEB_DEV_PLAN.md`（6周，6个阶段）

## 重要提示

- **金融风控敏感数据**：需要谨慎处理，注意数据安全
- **印尼用户隐私**：数据涉及印尼用户个人信息，注意合规
- **特征设计要结合实际**：需要结合印尼现金贷业务常识
- **FDC变量是历史已有特征**：新增特征需要去重检查
- **HTML报告要清晰**：展示特征质量指标（IV、PSI、覆盖率）
- **防穿越是核心**：特征工程必须实现防穿越机制
- **服务要稳定**：线上接口需要保证稳定性
- **先做首贷客户**：避免首贷复贷混合影响效果

## LLM模型配置（OpenRouter）

所有Agent统一通过 **OpenRouter** 接入 **qwen3.6-plus** 模型。

### API配置

```bash
# 环境变量设置
export OPENROUTER_API_KEY="your_api_key_here"
export LLM_MODEL="qwen3.6-plus"
```

### API端点

- **Base URL**: `https://openrouter.ai/api/v1`
- **Model**: `qwen3.6-plus`（或完整ID如 `qwen/qwen3.6-plus`）
- **认证**: Bearer Token（OPENROUTER_API_KEY）

### 代码示例

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

response = client.chat.completions.create(
    model="qwen/qwen3.6-plus",  # OpenRouter可能需要provider前缀
    messages=[{"role": "user", "content": prompt}],
    temperature=0,
    max_tokens=8000
)
```

### 更新utils/llm_client.py

```python
self.client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)
self.model = "qwen/qwen3.6-plus"  # 或根据OpenRouter实际ID调整
```
