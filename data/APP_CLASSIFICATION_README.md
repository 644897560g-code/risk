# APP 分类模块说明

这些文件是 APP 分类子系统的一部分，因此刻意保留在 `data/` 目录下，而不是归档到 `scripts/one_off/`。

- `rule_engine_classifier.py`：在线分类器，负责缓存查询和规则引擎判定，用于识别已知 APP 和新出现的 APP。
- `batch_classify_new_apps.py`：离线/夜间批量分类任务，用于处理白天积累的 unknown APP。
- `rule_learner.py` 和 `rule_learner_llm.py`：规则学习工具，用于从已分类样本中提取或更新分类规则。
- `validate_rule_engine.py`：规则引擎验证工具，用于检查分类规则效果。

当前特征流程会读取 APP 分类产物作为输入。
除非在线/离线 APP 分类方案已经被替换，否则不要在清理一次性脚本时删除这些模块。

