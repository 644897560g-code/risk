# 数据流注册表设计总结

**日期**: 2026-05-04
**问题**: Agent之间通过hardcoded文件路径传递，缺乏版本管理和依赖追踪

## 核心改进

### 之前的问题

```python
# ❌ Hardcoded文件路径
class FeatureReviewAgent:
    def load_code(self):
        with open('outputs/feature_code/features_calculator_v2.py') as f:
            code = f.read()  # 假设文件总是这个路径

class FeatureEngineeringAgent:
    def run(self):
        with open('outputs/feature_design/feature_design_doc.json') as f:
            design = json.load(f)  # 假设文件总是这个路径
```

**问题**:
- 文件路径变化需要修改所有相关Agent
- 审核重试时无法区分不同版本的代码
- 断点续做时无法恢复正确的文件依赖
- 无法追踪"这个Agent用的输入是哪个版本"

### 解决方案：DataFlowRegistry

```python
# ✅ 通过数据流注册表管理
class DataFlowRegistry:
    def register_execution(self, agent_name, inputs, outputs):
        """记录每次Agent执行的输入输出"""
        self.registry['agent_executions'].append({
            'agent_name': agent_name,
            'timestamp': datetime.now().isoformat(),
            'inputs': inputs,
            'outputs': outputs,
            'metadata': {...}
        })
        # 更新最新输出
        for name, path in outputs.items():
            self.registry['latest_outputs'][name] = path
```

**使用方式**:
```python
# 特征工程Agent执行后注册
data_flow.register_execution(
    agent_name='feature_engineering',
    inputs={'feature_design_doc': design_doc_path},
    outputs={'features_calculator': code_path}
)

# 特征审核Agent从注册表获取
code_file = data_flow.get_latest_output('features_calculator')
review_agent.code_path = code_file
```

## 数据流示例

一次完整执行的 `data_flow_registry.json`:

```json
{
  "agent_executions": [
    {
      "agent_name": "feature_design",
      "timestamp": "2026-05-04T10:30:00",
      "inputs": {
        "knowledge_base": "outputs/knowledge_base/knowledge_base.json"
      },
      "outputs": {
        "feature_design_doc": "outputs/feature_design/feature_design_doc.json"
      }
    },
    {
      "agent_name": "feature_engineering",
      "timestamp": "2026-05-04T10:35:00",
      "inputs": {
        "feature_design_doc": "outputs/feature_design/feature_design_doc.json"
      },
      "outputs": {
        "features_calculator": "outputs/feature_code/features_calculator_v2.py"
      }
    },
    {
      "agent_name": "feature_review",
      "timestamp": "2026-05-04T10:40:00",
      "inputs": {
        "features_calculator": "outputs/feature_code/features_calculator_v2.py"
      },
      "outputs": {
        "review_result": "outputs/feature_code/review_result.json",
        "review_report": "outputs/feature_code/review_report.md"
      },
      "metadata": {"status": "rejected"}
    },
    {
      "agent_name": "feature_engineering",
      "timestamp": "2026-05-04T10:45:00",
      "inputs": {
        "feature_design_doc": "outputs/feature_design/feature_design_doc.json",
        "review_feedback": "outputs/feature_code/review_result.json"
      },
      "outputs": {
        "features_calculator": "outputs/feature_code/features_calculator_v2.py"
      },
      "metadata": {"status": "regenerated_with_feedback", "retry_count": 1}
    }
  ],
  "latest_outputs": {
    "feature_design_doc": "outputs/feature_design/feature_design_doc.json",
    "features_calculator": "outputs/feature_code/features_calculator_v2.py",
    "review_result": "outputs/feature_code/review_result.json",
    "review_report": "outputs/feature_code/review_report.md"
  }
}
```

## 关键优势

| 维度 | Hardcoded路径 | DataFlowRegistry |
|------|--------------|------------------|
| 可追踪性 | ❌ 不知道用的哪个文件 | ✅ 完整执行历史 |
| 版本管理 | ❌ 无法区分版本 | ✅ 每次执行都有记录 |
| 断点续做 | ❌ 只能从固定位置 | ✅ 根据历史恢复 |
| 调试能力 | ❌ 难以定位问题 | ✅ 输入输出一目了然 |

## 文件变更清单

| 文件 | 修改内容 |
|------|---------|
| `agents/feature_orchestrator.py` | 新增 `DataFlowRegistry` 类，修改各Agent运行方法 |
| `outputs/feature_code/data_flow_registry.json` | 新建 - 数据流注册表文件 |
| `outputs/feature_code/DATA_FLOW_REGISTRY.md` | 新建 - 详细使用文档 |
| `CLAUDE.md` | 更新 - 添加数据流注册表说明 |

## 与状态文件的关系

```
orchestrator_state.json          data_flow_registry.json
┌────────────────────────┐      ┌──────────────────────────┐
│ current_step: "review" │      │ agent_executions: [...] │
│ status: "running"      │      │ latest_outputs: {...}   │
│ retry_count: 1         │      │                         │
│ completed_steps: [...]  │      │ 记录所有Agent的         │
│                        │      │ 输入输出文件路径         │
└────────────────────────┘      └──────────────────────────┘

     流程状态管理                       数据依赖管理
```

两者配合使用：
- `orchestrator_state.json`: 记录"做到哪一步了"
- `data_flow_registry.json`: 记录"用的是哪个文件"

## 经验教训

> **核心教训**: Agent之间的数据传递应该通过**注册表管理**，而非hardcoded文件路径。

这保证了：
1. **可追溯**: 知道每个Agent用了什么输入、产出了什么
2. **版本化**: 审核重试时能区分不同版本
3. **断点续做**: 根据历史记录恢复正确的依赖关系
4. **调试友好**: 数据流一目了然

## 后续扩展

当前实现了基础的数据流注册表，未来可以扩展：
- 支持多个并行分支的数据流
- 自动检测循环依赖
- 可视化数据流图
- 文件变更检测（如果输入文件变了，自动触发重新执行）

---

**相关文档**:
- `outputs/feature_code/DATA_FLOW_REGISTRY.md` - 详细使用文档
- `agents/feature_orchestrator.py` - 代码实现
- `CLAUDE.md` - 整体架构说明
