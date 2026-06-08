"""
测试20个样本的分类效果

验证类别定义、优先级和示例是否正确
"""

import sys
import os
import json
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

from utils.llm_client import LLMClient
from batch_classify_all_apps import create_batch_prompt

def main():
    print("="*80)
    print("测试20个样本的分类效果")
    print("="*80)

    # 1. 读取测试数据
    test_apps_df = pd.read_csv('outputs/app_classification/test_20_apps.csv')
    test_apps = test_apps_df.to_dict('records')

    print(f"\n测试样本: {len(test_apps)}个应用")

    # 2. 生成prompt
    system_prompt, user_prompt = create_batch_prompt(test_apps)

    print(f"\nPrompt长度: system={len(system_prompt)}, user={len(user_prompt)}")

    # 3. 调用LLM
    client = LLMClient()

    print(f"\n调用LLM进行分类...")
    response = client.chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0
    )

    # 4. 解析结果
    print(f"\n解析LLM响应...")

    # 提取JSON
    json_text = response
    if "```json" in response:
        json_text = response.split("```json")[1].split("```")[0].strip()
    elif "```" in response:
        json_text = response.split("```")[1].split("```")[0].strip()

    last_brace = json_text.rfind('}')
    if last_brace != -1:
        json_text = json_text[:last_brace + 1]

    try:
        result = json.loads(json_text)
        classifications = result.get('classifications', {})

        print(f"✓ 成功分类 {len(classifications)} 个应用\n")

        # 5. 打印结果
        print("="*100)
        print(f"{'应用包名':60s} {'类别':20s} {'置信度':8s} {'理由'}")
        print("="*100)

        for app_name, info in classifications.items():
            category = info.get('category', 'N/A')
            confidence = info.get('confidence', 'N/A')
            reason = info.get('reason', 'N/A')

            # 截断过长的应用名
            display_name = app_name[:58] if len(app_name) > 60 else app_name
            print(f"{display_name:60s} {category:20s} {confidence:8s} {reason}")

        # 6. 类别分布统计
        from collections import Counter
        categories = [info['category'] for info in classifications.values()]
        cat_counts = Counter(categories)

        print(f"\n类别分布:")
        for cat, count in cat_counts.most_common():
            print(f"  {cat:25s}: {count}个")

        # 7. 保存结果
        result_path = 'outputs/app_classification/test_20_result.json'
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump({
                'classifications': classifications,
                'raw_response': response
            }, f, ensure_ascii=False, indent=2)

        print(f"\n✓ 结果已保存: {result_path}")

        # 8. 检查是否有问题
        print(f"\n检查结果质量:")

        # 检查类别一致性
        unknown_cats = [cat for cat in categories if cat not in [
            'cash_loan', 'fintech_lending', 'gambling', 'fake_gps', 'app_store',
            'clone_app', 'banking', 'ewallet', 'installment', 'shopping',
            'transportation', 'food_delivery', 'utility', 'social_entertainment',
            'productivity', 'religious', 'other'
        ]]

        if unknown_cats:
            print(f"  ⚠ 发现未知类别: {set(unknown_cats)}")
        else:
            print(f"  ✓ 所有类别都在标准列表中")

        # 检查是否所有应用都被分类
        if len(classifications) == len(test_apps):
            print(f"  ✓ 所有{len(test_apps)}个应用都已分类")
        else:
            print(f"  ⚠ 只分类了{len(classifications)}/{len(test_apps)}个应用")

    except Exception as e:
        print(f"✗ 解析失败: {e}")
        print(f"\n原始响应预览:")
        print(response[:1000])


if __name__ == '__main__':
    main()
