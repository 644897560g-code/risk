# 主Agent流程编排指南（Orchestrator Knowledge Base）

**目标读者**: FeatureOrchestrator（主协调Agent）
**用途**: 记录影响整个特征工程流程的关键决策点和故障排查指南
**更新频率**: 每次遇到新的流程级问题时更新

---

## 一、流程依赖关系图

### 当前v2/v3主流程（2026-06-08归档后）

```
数据准备/知识缓存（离线或历史产物）
  ↓
┌─ FeatureOrchestrator ─────────────────────────────┐
│  入口: agents/feature_orchestrator.py              │
│  状态: outputs/feature_code/orchestrator_state.json │
└────────────┬──────────────────────────────────────┘
             ▼
┌─ FeatureDevelopmentAgent ─────────────────────────┐
│  合并: 特征设计 + 特征工程 + self-review            │
│  依赖: SkillRegistry + 通道1模板 + 通道2推理         │
└────────────┬──────────────────────────────────────┘
             ▼
┌─ FeatureMassProducer / FeatureEvaluator ──────────┐
│  产出: features_calculator_v2.py + IV/PSI报告       │
└────────────┬──────────────────────────────────────┘
             ▼
┌─ Feedback Aggregation + FeatureDeploymentAgent ───┐
│  反馈: iv_psi_feedback_rN.json                     │
│  部署: outputs/deployment/v*/                       │
└───────────────────────────────────────────────────┘
```

目录边界：
- 当前主链路在 `agents/feature_orchestrator.py`、`agents/feature_development_agent.py`、`agents/feature_mass_producer.py`、`agents/feature_evaluation_agent.py`、`agents/feature_deployment_agent.py`
- 旧版分离式Agent已归档到 `agents/legacy/`
- 一次性数据处理/debug脚本已归档到 `scripts/one_off/`
- APP分类基础设施仍保留在 `data/`，详见 `data/APP_CLASSIFICATION_README.md`

### 历史v1流程（仅供理解旧文档和旧代码）

```
数据准备（离线，不在此流程）
  ↓
┌─ 数据分析Agent ─────────┐
│  依赖: 原始数据 + 好坏标签  │
│  输出: 业务知识库          │
└────────────┬─────────────┘
             │ 业务知识库
             ▼
┌─ 特征设计Agent ─────────┐
│  依赖: 业务知识库 + FDC清单 │
│  输出: 特征设计文档JSON    │
│  ⚠️ 关键: Prompt必须完整  │
└────────────┬─────────────┘
             │ 特征设计JSON
             ▼
┌─ 特征工程Agent ─────────┐
│  依赖: 特征设计JSON       │
│  输出: 特征计算Python代码  │
│  ⚠️ 核心: 动态生成非硬编码 │
└────────────┬─────────────┘
             │ 特征代码
             ▼
┌─ 特征审核Agent ─────────┐
│  依赖: 特征代码           │
│  输出: 审核报告 + 反馈JSON │
│  ⚠️ 含: 语法/逻辑/LLM审核  │
└────────────┬─────────────┘
             │ 审核结果
             ▼
    【人工确认环节 yes/no】
             │
             ▼
┌─ 特征评估Agent ─────────┐
│  依赖: 审核通过的代码      │
│  输出: IV/PSI报告         │
└─────────────────────────┘
```

---

## 二、关键经验与约束

### 2.1 特征工程5大核心教训（不可违背）

> **来源**: `LESSONS_LEARNED.md` - "2026-05-04: 特征工程5大核心教训"

#### 教训1: 特征代码必须动态生成
- **原则**: 特征工程Agent是代码生成器，不是硬编码器
- **检查点**: 如果生成的代码中出现硬编码的feature_1/2/3，说明失败了
- **正确模式**: 从特征设计文档的`calculation_logic`字段生成代码

#### 教训2: 应用分类必须动态提取
- **原则**: 所有类别从`app_classification_cache`提取，不hardcoded
- **错误示例**: `STANDARD_CATEGORIES = {'gambling', 'cash_loan', ...}`
- **正确模式**: `_extract_standard_categories()` 从缓存动态读取
- **为什么重要**: 分类结果更新后代码自动同步，无需修改

#### 教训3: 防穿越时间过滤
- **原则**: 只能用applyTime之前的数据
- **applist**: 同时检查inTime AND upTime <= applyTime
- **FDC**: 只使用tgl_penyaluran_dana <= applyTime的贷款
- **时间窗口**: 从applyTime往前推（timedelta），不用当前系统时间

#### 教训4: 从原始数据开始计算
- **原则**: 所有特征从原始JSON计算，不假设预计算字段
- **错误示例**: `data.get('gambling_count', 0)` （不存在的字段）
- **正确模式**: 遍历appList，分类统计，实时计算

#### 教训5: FDC字段名必须正确
- **原则**: 必须先对照实际JSON结构确认字段名
- **常见错误**:
  - `'last_3days'` → 正确: `'3_hari'`
  - `'count'` → 正确: `'jumlahPlatformAktif'`
  - `'pinjaman_count'` → 正确: 遍历`pinjaman[]`列表

---

### 2.2 特征设计Prompt必须完整

> **来源**: `LESSONS_LEARNED.md` - "2026-05-04: 特征设计Agent的Prompt必须包含完整业务数据"

#### 核心教训
> **Prompt设计必须"数据驱动"，而非"描述驱动"**
>
> - ❌ 不要说："婚姻状态影响风险"（太抽象）
> - ✅ 要说："已婚逾期率14.29%，未婚逾期率38.46%"（具体数据）

#### 主Agent检查点
在调用特征设计Agent之前，确认Prompt包含：
- [ ] 职业风险分布（代码 + 逾期率）
- [ ] 婚姻风险分布
- [ ] 年龄风险分布
- [ ] 应用类别体系（16个标准类别）
- [ ] 完整FDC指标（11个统计指标）

---

### 2.3 审核不通过的循环重试机制（历史v1）

> **来源**: `REVIEW_FEEDBACK_LOOP.md`
> 当前v2/v3流程已移除独立 `FeatureReviewAgent`，改由 `FeatureDevelopmentAgent` self-review、`agents/code_ast_verifier.py` 和post_hook校验承接。

#### 重试流程
```
特征工程 → 审核 → ❌ 未通过
  ↓
保存 review_result.json （包含问题和anomal）
  ↓
主Agent检测 retry_count < 3
  ↓
特征工程.load_review_feedback()  ← 关键步骤
  ↓
特征工程.regenerate_with_feedback() ← LLM理解问题并修复
  ↓
重新审核
```

#### 主Agent需要做的
1. **检测重试场景**: `review_retry_count > 0` 且 `feature_engineering` 已在completed_steps中
2. **调用新方法**: `_run_feature_engineering_with_feedback()` 而非普通的 `_run_feature_engineering()`
3. **传递审核反馈**: FeatureEngineeringAgent读取 `review_result.json` 并自主修复

#### 重试配置
- `max_review_retries = 3`: 最多3次
- 3次后仍失败 → 建议人工介入

---

### 2.4 LLM调用成本控制

> **来源**: `LESSONS_LEARNED.md` - "2026-04-25: LLM调用不能发送原始数据"

#### 核心教训
**发送统计摘要而非原始数据**

- ✅ **DO**: 发送pre-computed aggregated statistics
- ❌ **DON'T**: 发送原始JSON或大量逐条记录

#### Token优化示例
| 场景 | 错误做法 | 正确做法 | Token节省 |
|------|---------|---------|----------|
| 应用分类 | 发送200个APP的完整JSON | 发送包名列表 | 98% |
| 特征设计 | 发送完整原始数据 | 发送聚合统计 | 95% |
| 特征工程 | 发送所有样本 | 发送数据结构示例 | 99% |

#### 主Agent检查点
在调用任何LLM相关Agent时，确认：
- [ ] 数据已预处理为摘要形式
- [ ] 没有发送完整的原始JSON
- [ ] temperature设置合理（通常0.1用于代码生成）

---

### 2.5 离线批量分类 vs 特征工程流程

> **来源**: `CLAUDE.md` - "离线批量APP分类 vs 特征工程主Agent"

#### 职责边界
| 维度 | 离线APP分类 | 特征工程主Agent |
|------|------------|----------------|
| 执行频率 | 每天凌晨 | 按需执行 |
| 触发方式 | 定时cron | 用户主动触发 |
| 依赖关系 | 独立 | 只读依赖分类结果 |

#### 关键实现
**特征计算器自动检测最新分类**:
```python
def _load_app_cache(self):
    # 自动查找最新的 classification_complete_*.json
    latest = max(cache_files, key=lambda f: os.path.getmtime(f))
```

这意味着：
- 离线分类每天产出新文件 → 无需修改代码
- 特征工程下次执行自动读取 → 完全解耦

---

## 三、故障排查指南

### 3.1 特征工程失败排查

**症状**: 生成的代码无法运行或有语法错误

**排查步骤**:
1. 检查审核报告: `outputs/feature_code/review_report.md`
2. 查看具体问题类型:
   - 语法错误 → 通常是LLM生成代码不完整
   - 逻辑错误 → 防穿越/硬编码/字段名问题
3. 确认是否已执行 `regenerate_with_feedback()`
4. 3次重试后仍失败 → 人工介入

**常见原因**:
- 特征设计文档不完整 → 检查步骤2的Prompt
- 分类缓存文件缺失 → 检查离线分类是否执行
- FDC字段名错误 → 检查 `LESSONS_LEARNED.md` 教训5

---

### 3.2 特征审核失败排查

**症状**: 语法或逻辑检查不通过

**常见原因**:

| 问题类型 | 常见原因 | 解决方案 |
|---------|---------|---------|
| datetime.now() | 代码中使用了当前时间 | 改为使用applyTime |
| 硬编码类别 | STANDARD_CATEGORIES = {...} | 改为动态提取 |
| 缺少防穿越 | 只过滤inTime | 同时过滤inTime和upTime |
| FDC字段错误 | last_3days, count | 改为3_hari, jumlahPlatformAktif |

---

### 3.3 断点续做策略

**何时使用**:
- 某一步骤失败需要跳过
- 人工修正后需要继续
- 想重新运行某个步骤

**使用方法**:
```bash
# 查看当前状态
python agents/feature_orchestrator.py --status

# 从特定步骤开始
python agents/feature_orchestrator.py --start-from feature_review
python agents/feature_orchestrator.py --start-from feature_engineering

# 重置整个流程
python agents/feature_orchestrator.py --reset
```

**状态文件**: `outputs/feature_code/orchestrator_state.json`

---

## 四、主Agent决策树

### 4.1 流程启动决策

```
用户运行 orchestrator.py
  ↓
检查状态文件是否存在？
  ├─ 是 → 检查completed_steps
  │       ↓
  │     从下一个未完成的步骤开始
  │
  └─ 否 → 从头开始
```

### 4.2 审核失败决策

```
审核结果 = False
  ↓
retry_count < 3？
  ├─ 是 → 打回特征工程 + 传递审核反馈
  │       ↓
  │     重新生成代码 → 重新审核
  │
  └─ 否 → 终止流程，建议人工修改
          ↓
        人工修改后 --start-from feature_review
```

### 4.3 人工确认决策

```
语法检查 ✓ AND 逻辑检查 ✓
  ↓
提示用户确认 (yes/no)
  ├─ yes → 最终通过
  └─ no  → 视为审核失败，进入重试循环
```

---

## 五、文档更新指南

### 何时更新本文档

添加新条目到 `LESSONS_LEARNED.md` 时，问自己：

1. **这个经验影响流程决策吗？**
   - 是 → 同时更新本文档的"关键经验"部分

2. **主Agent需要做不同的事吗？**
   - 是 → 更新本文档的"决策树"或"故障排查"部分

3. **这影响Agent之间的调用关系吗？**
   - 是 → 更新本文档的"流程依赖关系图"部分

### 与 LESSONS_LEARNED.md 的区别

| 文档 | 受众 | 内容类型 | 更新频率 |
|------|------|---------|---------|
| `LESSONS_LEARNED.md` | 所有开发者 | 详细的技术踩坑 | 高 |
| `AGENT_ORCHESTRATOR_LESSONS.md` | 主Agent | 流程级决策指南 | 中（只收录影响流程的） |

---

## 六、相关文档索引

- `LESSONS_LEARNED.md` - 完整的技术踩坑经验
- `CLAUDE.md` - 项目整体架构
- `DEV_PLAN.md` - 当前开发进度
- `REVIEW_FEEDBACK_LOOP.md` - 审核反馈循环机制
- `outputs/feature_code/FEATURE_REVIEW_IMPROVEMENTS.md` - 审核改进总结
- `outputs/feature_code/FEATURE_ENGINEERING_CHECKLIST.md` - 特征工程检查清单

---

**最后更新**: 2026-05-04（初始创建）
**维护者**: 特征工程团队
