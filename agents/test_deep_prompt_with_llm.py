import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.feature_design_deep_prompt import build_deep_business_prompt
from utils.llm_client import LLMClient


print("=" * 70)
print("测试深度业务Prompt + LLM生成")
print("=" * 70)

# 1. Load data
print("\n1. 加载数据...")
kb = json.load(open('outputs/knowledge_base/knowledge_base.json', 'r'))
import pandas as pd
df = pd.read_excel('FDC4710变量.xlsx')
fdc_vars = df['Feature Name'].tolist()
print(f"   知识库: {kb['knowledge_base']['summary']['total_samples']}样本")
print(f"   FDC变量: {len(fdc_vars)}个")

# 2. Build prompt
print("\n2. 构建Prompt...")
prompt = build_deep_business_prompt(kb, fdc_vars)
print(f"   长度: {len(prompt)}字符")

# 3. Call LLM
print("\n3. 调用LLM生成特征框架...")
llm = LLMClient()
messages = [{"role": "user", "content": prompt}]

print("   生成中...")
response = llm.chat(messages, temperature=0.3)
print(f"   ✅ 响应: {len(response)}字符")

# 4. Extract JSON
print("\n4. 提取JSON...")
json_start = response.find('{')
json_end = response.rfind('}') + 1
if json_start >= 0:
    json_str = response[json_start:json_end]
    try:
        framework = json.loads(json_str)

        os.makedirs('outputs/feature_design', exist_ok=True)
        output = 'outputs/feature_design/feature_framework_deep.json'
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(framework, f, ensure_ascii=False, indent=2)

        print(f"   ✅ 保存到: {output}")

        # Stats
        fw = framework.get('feature_framework', {})
        cats = fw.get('template_categories', [])
        print(f"\n5. 框架统计:")
        print(f"   类别数: {len(cats)}")
        for cat in cats:
            templates = len(cat.get('templates', []))
            rationale = cat.get('business_rationale', '')[:50]
            print(f"   - {cat['category_name']}: {templates}模板")
            print(f"     业务依据: {rationale}...")

        print("\n" + "=" * 70)
        print("✅ 测试成功!")
        print("=" * 70)

    except json.JSONDecodeError as e:
        print(f"   ❌ JSON失败: {e}")
        print(f"   预览: {json_str[:800]}")
else:
    print("   ❌ 未找到JSON")
    print(f"   响应: {response[:800]}")
