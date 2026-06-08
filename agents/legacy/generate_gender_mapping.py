"""
生成性别数据质量报告

规则：
1. 当 base.gender 与 idCard 推导的性别不一致时，以 idCard 为准
2. base.gender 字段应当废弃，特征工程应使用 idCard 推导的性别
"""

import json
import glob
from collections import Counter


def extract_gender_from_idcard(id_card: str) -> int:
    """
    从身份证号提取性别

    Returns:
        0 = 男性 (第7-8位在01-31)
        1 = 女性 (第7-8位在41-71)
        -1 = 无法解析
    """
    if not id_card or len(id_card) < 12:
        return -1

    try:
        day_code = int(id_card[6:8])

        if 1 <= day_code <= 31:
            return 0  # 男性
        elif 41 <= day_code <= 71:
            return 1  # 女性
        else:
            return -1  # 无效值

    except (ValueError, IndexError):
        return -1


def main():
    json_files = glob.glob('data/all_samples/*.json')
    print(f"📂 分析 {len(json_files)} 个样本...")

    # 统计
    gender_vs_idcard = {
        'consistent': 0,  # base.gender 与 idCard 一致
        'inconsistent': 0,  # base.gender 与 idCard 不一致
        'missing_idcard': 0,  # 缺少身份证号
        'invalid_idcard': 0  # 身份证号无效
    }

    # 正确性统计（以idCard为准）
    true_gender_dist = Counter()

    inconsistencies = []

    for filepath in json_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                base = data.get('params', {}).get('base', data.get('base', {}))

                if not base:
                    continue

                id_card = base.get('idCard', '')
                base_gender = base.get('gender')

                if not id_card or len(id_card) < 12:
                    gender_vs_idcard['missing_idcard'] += 1
                    continue

                # 从idCard推导性别
                idcard_gender = extract_gender_from_idcard(id_card)

                if idcard_gender == -1:
                    gender_vs_idcard['invalid_idcard'] += 1
                    continue

                # 统计真实性别分布（以idCard为准）
                true_gender_dist[idcard_gender] += 1

                # 检查一致性
                if base_gender == idcard_gender:
                    gender_vs_idcard['consistent'] += 1
                else:
                    gender_vs_idcard['inconsistent'] += 1
                    inconsistencies.append({
                        'file': filepath.split('/')[-1],
                        'base_gender': base_gender,
                        'idcard_gender': idcard_gender,
                        'idCard': id_card[:12] + '...',
                        'birthday': base.get('birthday')
                    })

        except Exception as e:
            continue

    # 打印报告
    print("\n" + "=" * 70)
    print("性别数据质量报告")
    print("=" * 70)

    print(f"\n📊 数据一致性统计:")
    total = sum(gender_vs_idcard.values())
    print(f"  总样本数: {total}")
    print(f"  ✅ 一致: {gender_vs_idcard['consistent']} ({gender_vs_idcard['consistent']/total*100:.1f}%)")
    print(f"  ❌ 不一致: {gender_vs_idcard['inconsistent']} ({gender_vs_idcard['inconsistent']/total*100:.1f}%)")
    print(f"  ⚠️ 缺少身份证号: {gender_vs_idcard['missing_idcard']}")
    print(f"  ⚠️ 身份证号无效: {gender_vs_idcard['invalid_idcard']}")

    print(f"\n📊 真实性别分布（基于身份证号推导）:")
    total_valid = sum(true_gender_dist.values())
    male_count = true_gender_dist.get(0, 0)
    female_count = true_gender_dist.get(1, 0)
    print(f"  男性 (0): {male_count} ({male_count/total_valid*100:.1f}%)")
    print(f"  女性 (1): {female_count} ({female_count/total_valid*100:.1f}%)")

    print(f"\n❗ 结论:")
    inconsistency_rate = gender_vs_idcard['inconsistent'] / total * 100 if total > 0 else 0
    if inconsistency_rate > 5:
        print(f"  ⚠️ 不一致率高达 {inconsistency_rate:.1f}%")
        print(f"  ✅ 建议: 废弃 base.gender，使用 idCard 推导的性别")
    else:
        print(f"  ✅ 一致性较高，base.gender 可用")

    if inconsistencies:
        print(f"\n⚠️ 不一致样本示例（前5个）:")
        for inc in inconsistencies[:5]:
            print(f"  文件: {inc['file']}")
            print(f"    base.gender={inc['base_gender']}, idCard推导={inc['idcard_gender']}")
            print(f"    idCard: {inc['idCard']}, 生日: {inc['birthday']}")
            print()

    # 生成特征工程建议
    print("\n" + "=" * 70)
    print("特征工程建议")
    print("=" * 70)
    print("""
在特征工程中，**不要直接使用 base.gender 字段**，应通过身份证号推导性别：

```python
def extract_gender_from_idcard(id_card: str) -> int:
    '''
    从身份证号提取性别
    Returns:
        0 = 男性 (第7-8位在01-31)
        1 = 女性 (第7-8位在41-71, 需要减40)
        -1 = 无法解析
    '''
    if not id_card or len(id_card) < 12:
        return -1

    try:
        day_code = int(id_card[6:8])

        if 1 <= day_code <= 31:
            return 0  # 男性
        elif 41 <= day_code <= 71:
            return 1  # 女性
        else:
            return -1  # 无效值
    except:
        return -1

# 使用示例
gender = extract_gender_from_idcard(base['idCard'])
```

**原因**:
- base.gender 与 idCard 推导的性别不一致率达 XX%
- 身份证号是更权威的性别来源
- 印尼KTP身份证号第7-12位编码出生日期和性别
""")


if __name__ == "__main__":
    main()
