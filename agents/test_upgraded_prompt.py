"""
测试升级后的特征设计Prompt

目标：生成100+高质量特征框架
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.llm_client import LLMClient
from feature_design_prompt_upgraded import build_upgraded_prompt


def test_new_prompt():
    """测试新Prompt效果"""
    print("=" * 70)
    print("测试升级版特征设计Prompt")
    print("=" * 70)

    # 加载知识库
    print("\n1. 加载知识库...")
    with open('outputs/knowledge_base/knowledge_base.json', 'r', encoding='utf-8') as f:
        kb = json.load(f)
    print(f"   ✅ 加载完成")

    # 加载FDC变量
    print("\n2. 加载FDC变量...")
    import pandas as pd
    df = pd.read_excel('FDC4710变量.xlsx')
    fdc_vars = df['Feature Name'].tolist()
    print(f"   ✅ 加载了 {len(fdc_vars)} 个FDC变量")

    # 构建Prompt
    print("\n3. 构建Prompt...")
    prompt = build_upgraded_prompt(kb, fdc_vars)
    print(f"   ✅ Prompt长度: {len(prompt)} 字符")

    # 调用LLM
    print("\n4. 调用LLM生成特征框架...")
    llm = LLMClient()

    messages = [{"role": "user", "content": prompt}]

    print("   🔄 正在生成中（可能需要几分钟）...")

    try:
        response = llm.chat(messages, temperature=0.3)
        print(f"   ✅ LLM响应收到（{len(response)} 字符）")

        # 提取JSON
        print("\n5. 提取JSON...")
        json_start = response.find('{')
        json_end = response.rfind('}') + 1

        if json_start >= 0:
            json_str = response[json_start:json_end]
            framework = json.loads(json_str)

            print(f"   ✅ JSON解析成功")
            print(f"   顶层键: {list(framework.keys())}")

            # 保存
            os.makedirs('outputs/feature_design', exist_ok=True)
            output_file = 'outputs/feature_design/feature_framework_v2.json'

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(framework, f, ensure_ascii=False, indent=2)

            print(f"\n   💾 已保存到: {output_file}")

            # 统计
            if 'feature_framework' in framework:
                fw = framework['feature_framework']
                meta = fw.get('meta', {})
                categories = fw.get('template_categories', [])

                print(f"\n   📊 框架统计:")
                print(f"      版本: {meta.get('version', 'N/A')}")
                print(f"      目标: {meta.get('target_total', 'N/A')}")
                print(f"      类别数: {len(categories)}")

                for cat in categories:
                    cat_name = cat.get('category_name', 'unknown')
                    expected = cat.get('expected_feature_count', 0)
                    templates = cat.get('templates', [])
                    print(f"      - {cat_name}: {len(templates)}模板, 预期{expected}特征")

            return True

        else:
            print(f"   ❌ 未找到JSON，响应预览: {response[:500]}")
            return False

    except json.JSONDecodeError as e:
        print(f"   ❌ JSON解析失败: {e}")
        print(f"   响应预览: {response[:1000]}")
        return False

    except Exception as e:
        print(f"   ❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = test_new_prompt()

    if success:
        print("\n" + "=" * 70)
        print("✅ Prompt测试成功!")
        print("=" * 70)
    else:
        print("\n" + "=" * 70)
        print("❌ Prompt测试失败!")
        print("=" * 70)