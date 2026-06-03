"""
展示LLM规则学习的实际Prompt - gambling类别示例
"""

import json
import sys
sys.path.append('/Users/apple/Desktop/agents/risk-agent-cc-indo')

# 加载数据
with open('outputs/app_analysis/classification_complete_11850.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

classifications = data['classifications']

# 提取gambling类别的样本
gambling_samples = []
for pkg_name, info in classifications.items():
    if info['category'] == 'gambling':
        gambling_samples.append({
            'package_name': pkg_name,
            'reason': info.get('reason', '')
        })

print(f"gambling类别共有 {len(gambling_samples)} 个样本\n")
print("=" * 100)
print("以下是发送给LLM的完整Prompt示例：\n")
print("=" * 100)

# 构建Prompt（显示前50个样本）
category = 'gambling'
max_samples = 50

prompt = f"""# 任务：从印尼APP样本中学习在线判定规则

## 背景
你正在分析印尼智能手机用户安装的应用程序包名（package names），需要从中识别出**{category}**类别的应用。

## 已知信息
- 这些应用都属于**{category}**类别
- 总样本数：{len(gambling_samples)}个（使用全部样本，非采样）
- 应用包名和说明如下（共{len(gambling_samples)}个，展示前{max_samples}个）：

"""

for i, sample in enumerate(gambling_samples[:max_samples], 1):
    prompt += f"{i}. 包名: `{sample['package_name']}`"
    if sample['reason']:
        prompt += f"\n   说明: {sample['reason']}"
    prompt += "\n"

prompt += f"""
## 你的任务

请从这些样本中总结出**在线判定规则**，使得系统能够实时判断一个新APP是否属于**{category}**类别。

## 输出要求

请输出JSON格式的规则（不要有其他文字）：

```json
{{
  "category": "{category}",
  "total_samples": {len(gambling_samples)},

  "keywords": {{
    "indonesian": ["关键词1", "关键词2", ...],
    "english": ["关键词1", "关键词2", ...],
    "description": "说明这些关键词为什么能区分{category}"
  }},

  "patterns": [
    {{
      "regex": "^正则表达式1$",
      "description_cn": "详细的中文描述，说明这个正则表达式匹配什么模式、为什么能识别{category}",
      "confidence": 0.9,
      "examples": ["匹配的包名示例1", "匹配的包名示例2"]
    }},
    ...
  ],

  "brands": [
    {{
      "name": "品牌名1",
      "description": "品牌说明",
      "confidence": 0.95
    }},
    ...
  ],

  "exclusion_rules": [
    {{
      "rule": "如果包含xxx词，则不属于{category}",
      "reason": "说明为什么"
    }},
    ...
  ],

  "confusion_risk": [
    {{
      "confused_with": "可能混淆的其他类别",
      "distinguishing_feature": "如何区分"
    }},
    ...
  ],

  "reasoning": "综合推理逻辑：为什么上述规则能准确判定{category}类别"
}}
```

## 重要指导原则

1. **正则表达式要求**（非常重要！）：
   - 必须是**合法的正则语法**（如 `^com\\.id\\d+\\..*` 或 `.*slot.*\\d+.*`）
   - 不能使用 `[WORD]`、`[NUM]`、`[SHORT]` 等抽象占位符（这些不是合法正则！）
   - 要精确到包名级别（如 `^com\\.higgs\\..*` 或 `^com\\.id5dan777\\..*`）
   - **每个正则必须配中文描述**（`description_cn`字段），说明这个正则是匹配什么模式

2. **关键词要求**：
   - 必须是**高区分度**的词（在{category}中常见，其他类别少见）
   - 不能有冲突词（如"game"在所有类别都有，不要用）
   - 优先选择印尼语特征词（如"judi", "pinjaman", "slot"）

3. **排除规则**：
   - 明确什么情况下**不应该**判定为{category}
   - 例如：如果包含"bank"，可能是banking而非fintech_lending

4. **置信度评估**：
   - 0.9-1.0: 几乎100%准确（如已知品牌）
   - 0.8-0.9: 高度可信（如明确关键词+模式）
   - 0.7-0.8: 较可信（如单一关键词）
   - <0.7: 需要人工审核

5. **易混淆处理**：
   - 说明可能与其他哪些类别混淆
   - 给出区分方法

## 开始

请分析上述样本，输出规则JSON：
"""

print(prompt)
print("=" * 100)
print(f"\nPrompt总长度: {len(prompt)} 字符")
print(f"预计Token消耗: ~{len(prompt) // 4} tokens（按每4字符约1token估算）")
