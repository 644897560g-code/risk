# 人工确认模式说明

**日期**: 2026-05-04
**问题**: 特征审核Agent在后台运行时会卡在`input()`等待人工输入

## 解决方案

特征审核Agent现在支持两种模式：

### 模式1：交互模式（默认）

```bash
python agents/feature_review_agent.py
# 或
python agents/feature_orchestrator.py
```

行为：
- 显示审核结果
- 等待用户输入`yes`或`no`
- 适合有前端交互的场景

### 模式2：自动确认模式

```bash
# 方式1：命令行参数
python agents/feature_review_agent.py --auto-confirm

# 方式2：环境变量
AUTO_CONFIRM_REVIEW=true python agents/feature_orchestrator.py
```

行为：
- 显示审核结果（不等待输入）
- 只要语法和逻辑检查通过就自动确认
- 适合后台测试/CI/无前端场景

## 使用场景对比

| 场景 | 推荐模式 | 配置 |
|------|---------|------|
| 本地开发调试 | 交互模式 | 默认 |
| 有前端UI | 交互模式 | 默认 |
| 后台自动运行 | 自动确认 | `--auto-confirm` |
| CI/CD测试 | 自动确认 | `AUTO_CONFIRM_REVIEW=true` |
| 端到端测试 | 自动确认 | `--auto-confirm` |

## 主Agent集成

主Agent会根据环境变量自动选择模式：

```python
# 检查环境变量
auto_confirm = os.getenv('AUTO_CONFIRM_REVIEW', 'false').lower() == 'true'

# 调用审核Agent
result = self.review_agent.run(auto_confirm=auto_confirm)
```

## 审核结果逻辑

### 交互模式
```
审核结果概要:
  - 语法检查: 通过
  - 逻辑检查: 通过
  - LLM评分: 82/100

请查看审核报告: outputs/feature_code/review_report.md
---------------------------------------

语法和逻辑检查通过。是否确认审核通过? (yes/no): yes

✅ 人工确认：审核通过
```

### 自动确认模式
```
⚠️  模式：自动确认（无人工交互）

审核结果概要:
  - 语法检查: 通过
  - 逻辑检查: 通过
  - LLM评分: 82/100

✅ 自动确认：审核通过（auto_confirm=True）
```

## 端到端测试示例

```bash
# 运行完整流程（不会卡住）
AUTO_CONFIRM_REVIEW=true python agents/feature_orchestrator.py

# 或者单独测试审核Agent
python agents/feature_review_agent.py --auto-confirm
```

## 相关环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `AUTO_CONFIRM_REVIEW` | 审核自动确认 | `false` |

## 最佳实践

1. **开发阶段**: 使用交互模式，人工检查审核结果
2. **测试阶段**: 使用自动确认，快速验证流程
3. **生产环境**: 根据是否有前端UI选择模式
4. **CI/CD**: 始终使用自动确认模式
