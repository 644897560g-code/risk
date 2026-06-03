# 数据流注册表（Data Flow Registry）

**日期**: 2026-05-04

## 问题背景

在主Agent协调的6个Agent流程中，每个Agent都有输入和输出文件：

```
数据分析 → 输出: knowledge_base.json
    ↓
特征设计 → 输入: knowledge_base.json
        → 输出: feature_design_doc.json
    ↓
特征工程 → 输入: feature_design_doc.json
        → 输出: features_calculator_v2.py
    ↓
特征审核 → 输入: features_calculator_v2.py
        → 输出: review_result.json + review_report.md
```

**之前的问题**:
- 每个Agent hardcoded文件路径
- 无法追踪某个Agent使用的是哪个版本的输入
- 审核重试时无法正确获取上一轮的反馈文件
- 断点续做时无法恢复正确的文件依赖关系

## 解决方案：数据流注册表

### 核心设计

`DataFlowRegistry` 类管理所有Agent执行的输入输出记录：

```python
class DataFlowRegistry:
    def __init__(self):
        self.registry_file = 'outputs/feature_code/data_flow_registry.json'
        self.registry = {
            'agent_executions': [],  # 每次执行的记录
            'latest_outputs': {}     # 每个Agent的最新输出
        }

    def register_execution(self, agent_name, inputs, outputs, metadata=None):
        """注册一次Agent执行"""
        execution = {
            'agent_name': agent_name,
            'timestamp': datetime.now().isoformat(),
            'inputs': inputs,      # {输入名称: 文件路径}
            'outputs': outputs,    # {输出名称: 文件路径}
            'metadata': metadata   # 额外信息
        }
        self.registry['agent_executions'].append(execution)

        # 更新最新输出
        for output_name, output_path in outputs.items():
            self.registry['latest_outputs'][output_name] = output_path

        self.save()
```

### 存储格式

`outputs/feature_code/data_flow_registry.json`:

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
      },
      "metadata": {
        "status": "completed"
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
      },
      "metadata": {
        "status": "completed"
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
      "metadata": {
        "status": "rejected",
        "human_confirmed": false
      }
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
      "metadata": {
        "status": "regenerated_with_feedback",
        "retry_count": 1
      }
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

### 使用方式

#### 1. 主Agent中注册执行

```python
def _run_feature_design(self) -> bool:
    try:
        self.design_agent.run()

        # 注册数据流
        self.data_flow.register_execution(
            agent_name='feature_design',
            inputs={'knowledge_base': 'outputs/knowledge_base/knowledge_base.json'},
            outputs={'feature_design_doc': 'outputs/feature_design/feature_design_doc.json'},
            metadata={'status': 'completed'}
        )
        return True
    except Exception as e:
        return False
```

#### 2. 获取最新输出作为下一个Agent的输入

```python
def _run_feature_engineering(self) -> bool:
    try:
        # 从数据流获取特征设计的输出
        design_doc = self.data_flow.get_latest_output(
            'feature_design_doc',
            default='outputs/feature_design/feature_design_doc.json'
        )

        # 使用design_doc作为输入...
        self.engineering_agent.load_feature_design(design_doc)
```

#### 3. 获取执行历史

```python
# 获取特征审核的所有执行记录
review_history = self.data_flow.get_execution_history('feature_review')

# 获取最后一次审核的结果
if review_history:
    latest_review = review_history[-1]
    review_status = latest_review['metadata']['status']  # 'approved' or 'rejected'
```

#### 4. 命令行查询

```bash
# 查看数据流注册表
cat outputs/feature_code/data_flow_registry.json | jq

# 查看某个Agent的执行历史
python -c "
from agents.feature_orchestrator import DataFlowRegistry
df = DataFlowRegistry()
history = df.get_execution_history('feature_engineering')
for h in history:
    print(f'{h[\"timestamp\"]}: {h[\"metadata\"]}')
"
```

### 关键优势

| 维度 | Hardcoded文件路径 | 数据流注册表 |
|------|------------------|-------------|
| **可追踪性** | ❌ 不知道用的哪个文件 | ✅ 完整的执行历史记录 |
| **版本管理** | ❌ 无法区分不同版本 | ✅ 每次执行都有记录 |
| **断点续做** | ❌ 只能从固定位置开始 | ✅ 根据历史记录恢复 |
| **调试能力** | ❌ 难以定位文件问题 | ✅ 输入输出一目了然 |
| **灵活性** | ❌ 修改路径需改多处 | ✅ 集中管理，易于修改 |

### 与状态文件的关系

`orchestrator_state.json` 和 `data_flow_registry.json` 分工：

| 文件 | 职责 | 内容 |
|------|------|------|
| `orchestrator_state.json` | 流程状态 | 当前步骤、完成状态、重试次数 |
| `data_flow_registry.json` | 数据依赖 | Agent输入输出文件路径 |

两者配合使用：
```python
# 主Agent加载状态
state = load_state()  # 从 orchestrator_state.json

# 同时加载数据流
data_flow = DataFlowRegistry()  # 从 data_flow_registry.json

# 断点续做时
if state['current_step'] == 'feature_review':
    # 从数据流获取待审核的文件
    code_file = data_flow.get_latest_output('features_calculator')
    review_agent.code_path = code_file
```

### 最佳实践

1. **每个Agent执行后必须注册**
   - 即使失败也要注册（记录失败状态）
   - 保证数据流完整

2. **使用有意义的输出名称**
   - `features_calculator` 而非 `code`
   - 便于理解和查询

3. **在metadata中记录关键信息**
   - 状态: `completed`, `failed`, `rejected`
   - 重试次数: `retry_count`
   - 人工确认: `human_confirmed`

4. **定期检查数据流完整性**
   ```bash
   python -c "
   from agents.feature_orchestrator import DataFlowRegistry
   df = DataFlowRegistry()
   print(f'Total executions: {len(df.registry[\"agent_executions\"])}')
   print(f'Latest outputs: {df.registry[\"latest_outputs\"]}')
   "
   ```

### 相关文件

- `agents/feature_orchestrator.py` - DataFlowRegistry类实现
- `outputs/feature_code/data_flow_registry.json` - 数据流注册表文件
- `outputs/feature_code/orchestrator_state.json` - 流程状态文件
