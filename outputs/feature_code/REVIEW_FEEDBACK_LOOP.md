# 审核反馈→特征工程自主修复循环机制

**日期**: 2026-05-04

## 问题背景

之前的实现中，当特征审核不通过时，主Agent只是简单地"重新运行特征工程"，但没有把审核意见反馈给特征工程Agent，导致它无法理解需要修复什么问题。

## 解决方案

实现了**审核反馈→自主修复→重新审核**的完整循环：

```
特征工程 → 生成代码 → 特征审核 → 发现问题
                                    ↓
                          保存审核反馈JSON
                                    ↓
                    主Agent检测到审核未通过
                                    ↓
                加载审核反馈 + 现有代码
                                    ↓
          特征工程Agent理解审核意见
                                    ↓
                LLM自主修复代码问题
                                    ↓
                        重新提交审核
                                    ↓
                          最多重试3次
```

## 技术实现

### 1. 特征工程Agent新增方法

**文件**: `agents/feature_engineering_agent_final.py`

#### `load_review_feedback(feedback_file)`
加载审核结果JSON文件

```python
def load_review_feedback(self, feedback_file: str = 'outputs/feature_code/review_result.json'):
    """加载审核反馈"""
    if os.path.exists(feedback_file):
        with open(feedback_file, 'r', encoding='utf-8') as f:
            self.review_feedback = json.load(f)
        return True
    return False
```

#### `regenerate_with_feedback(existing_code)`
使用审核反馈重新生成代码

```python
def regenerate_with_feedback(self, existing_code: str) -> str:
    """使用审核反馈重新生成代码"""
    # 提取审核问题
    logic_issues = self.review_feedback.get('logic_check', {}).get('issues', [])
    llm_suggestions = self.review_feedback.get('llm_review', {}).get('suggestions', [])
    syntax_errors = self.review_feedback.get('syntax_check', {}).get('errors', [])

    # 构建修复prompt
    prompt = self._build_regeneration_prompt(existing_code, syntax_errors, logic_issues, llm_suggestions)

    # LLM修复代码
    response = self.llm_client.chat(messages, temperature=0.1)
    return self._extract_code(response)
```

#### `_build_regeneration_prompt(...)`
构建修复prompt，包含：
- 原始代码
- 语法错误列表
- 逻辑问题列表
- LLM改进建议

### 2. 主Agent新增流程

**文件**: `agents/feature_orchestrator.py`

#### 状态检测
```python
elif self.review_retry_count > 0:
    # 重试情况：使用审核反馈重新生成
    self._log("  检测到审核重试，加载审核反馈...")
    result = self._run_feature_engineering_with_feedback()
```

#### 带反馈的重新生成
```python
def _run_feature_engineering_with_feedback(self) -> bool:
    """运行特征工程Agent（带审核反馈的重新生成）"""
    # 1. 加载现有的代码
    with open(code_file, 'r', encoding='utf-8') as f:
        existing_code = f.read()

    # 2. 加载审核反馈
    self.engineering_agent.load_review_feedback()

    # 3. 使用反馈重新生成代码
    new_code = self.engineering_agent.regenerate_with_feedback(existing_code)

    # 4. 保存新代码
    self.engineering_agent.save_code(new_code)
    return True
```

## 执行流程示例

### 第1次尝试（审核失败）
```
【步骤3/5】特征工程Agent
  → 生成 features_calculator_v2.py

【步骤4/5】特征审核Agent（第1次尝试）
  → 发现问题:
     - 禁止使用当前系统时间（应使用applyTime）
     - 发现硬编码类别

❌ 审核未通过，打回特征工程重新开发（第1/3次重试）
```

### 第2次尝试（带反馈修复）
```
【步骤3/5】特征工程Agent（重新开发）
  → 检测到审核重试，加载审核反馈...
  → Loaded review feedback from review_result.json
  → Regenerating code with review feedback...
  → LLM理解问题并修复代码
  → 代码已根据审核反馈重新生成

【步骤4/5】特征审核Agent（第2次尝试）
  → 检查修复后的代码...
  → ✅ 审核通过
```

## 配置文件

### 审核反馈JSON格式
`outputs/feature_code/review_result.json`:
```json
{
  "syntax_check": {
    "passed": true,
    "errors": []
  },
  "logic_check": {
    "passed": false,
    "issues": [
      "禁止使用当前系统时间（应使用applyTime）",
      "发现硬编码类别: 'gambling', 'cash_loan'"
    ]
  },
  "llm_review": {
    "score": 65,
    "suggestions": [
      "移除datetime.now()，改用applyTime",
      "从配置动态加载类别列表"
    ]
  }
}
```

## 关键优势

1. **自主理解**: 特征工程Agent通过LLM理解审核意见
2. **精准修复**: 只修复报告的问题，保持其他逻辑不变
3. **迭代优化**: 支持最多3次重试，每次都有新的修复机会
4. **人工兜底**: 3次重试后仍失败，建议人工介入

## 限制条件

- LLM修复能力取决于问题的复杂度
- 复杂问题可能需要人工修改prompt或手动修复
- 每次重试消耗LLM token

## 适用场景

- 语法错误修复
- 逻辑问题修正（防穿越、硬编码等）
- 代码质量改进（异常处理、边界条件等）
- 字段名修正

## 相关文件

- `agents/feature_engineering_agent_final.py` - 带反馈的代码生成
- `agents/feature_orchestrator.py` - 主Agent循环逻辑
- `agents/feature_review_agent.py` - 审核反馈生成
- `outputs/feature_code/review_result.json` - 审核反馈文件
