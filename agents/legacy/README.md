# 旧版 Agent 目录

这个目录用于保存旧版 Agent 实现，主要用于历史追溯、复现实验结果和排查旧流程问题。
这些文件已经不属于当前 v2 主运行链路。

当前主运行链路请优先查看：

- `agents/feature_orchestrator.py`
- `agents/feature_development_agent.py`
- `agents/feature_mass_producer.py`
- `agents/feature_evaluation_agent.py`
- `agents/feature_deployment_agent.py`
- `agents/template_generation_agent.py`

本目录中的旧代码主要包括：

- 早期分离式的数据分析、特征设计、特征工程、特征审核 Agent
- Prompt 实验脚本，以及一次性的 FDC/性别字段分析工具
- 早期特征工程实现，用于对比或复查历史逻辑

注意：`feature_engineering_agent_v2.py.txt` 是一个保留下来的历史坏样本。
它没有继续作为 `.py` 模块保存，是因为原始文件中的 prompt 字符串边界损坏，Python 无法正常解析。

除非是在复现旧流程或挖掘历史逻辑，否则不要基于本目录继续开发新功能。
新代码应接入上面列出的当前主运行链路。

