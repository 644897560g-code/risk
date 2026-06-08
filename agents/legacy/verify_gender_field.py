"""
验证base.gender字段的正确性

通过身份证号(idCard)第7-12位推导性别，与base.gender字段对比验证

性别判断规则（印尼KTP身份证号）：
- 第7-12位编码出生日期
- 男性：第7-8位 = 实际出生日期（01-31）
- 女性：第7-8位 = 实际出生日期 + 40（即41-71）
"""

import json
import glob
from collections import Counter


def extract_gender_from_idcard(id_card: str) -> int:
    """
    从身份证号提取性别

    Returns:
        0 = 男性 (第7-8位在01-31)
        1 = 女性 (第7-8位在41-71, 需要减40)
        -1 = 无法解析
    """
    if not id_card or len(id_card) < 12:
        return -1

    try:
        # 第7-8位（索引从0开始，所以是6:8）
        day_code = int(id_card[6:8])

        if 1 <= day_code <= 31:
            return 0  # 男性
        elif 41 <= day_code <= 71:
            return 1  # 女性
        else:
            return -1  # 无效值

    except (ValueError, IndexError):
        return -1


def verify_gender_field(samples_dir: str = "data/all_samples"):
    """验证gender字段"""

    json_files = glob.glob(f"{samples_dir}/*.json")
    print(f"📂 找到 {len(json_files)} 个样本文件")

    # 统计计数器
    gender_counter = Counter()  # base.gender分布
    idcard_gender_counter = Counter()  # 从idCard推导的性别分布
    match_counter = {"match": 0, "mismatch": 0, "skip": 0}

    mismatches = []  # 记录不匹配的样本

    for filepath in json_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                base = data.get('params', {}).get('base', data.get('base', {}))

                if not base:
                    continue

                gender = base.get('gender')
                id_card = base.get('idCard', '')

                if gender is None or not id_card:
                    match_counter['skip'] += 1
                    continue

                # 从idCard推导性别
                idcard_gender = extract_gender_from_idcard(id_card)

                if idcard_gender == -1:
                    match_counter['skip'] += 1
                    continue

                # 统计
                gender_counter[gender] += 1
                idcard_gender_counter[idcard_gender] += 1

                # 验证是否匹配
                if gender == idcard_gender:
                    match_counter['match'] += 1
                else:
                    match_counter['mismatch'] += 1
                    mismatches.append({
                        'file': filepath.split('/')[-1],
                        'gender': gender,
                        'idcard_gender': idcard_gender,
                        'idCard': id_card,
                        'birthday': base.get('birthday')
                    })

        except Exception as e:
            print(f"  ⚠️ 处理文件失败 {filepath}: {e}")
            continue

    # 打印结果
    print("\n" + "=" * 70)
    print("Gender字段验证结果（基于身份证号交叉验证）")
    print("=" * 70)

    print(f"\n📊 样本统计:")
    print(f"  总样本数: {len(json_files)}")
    print(f"  有效样本: {sum(gender_counter.values())}")
    print(f"  跳过样本: {match_counter['skip']}")

    print(f"\n📊 base.gender 分布:")
    for gender, count in sorted(gender_counter.items()):
        pct = count / sum(gender_counter.values()) * 100
        label = "女" if gender == 0 else "男" if gender == 1 else "未知"
        print(f"  gender={gender} ({label}): {count} ({pct:.1f}%)")

    print(f"\n📊 idCard推导性别分布:")
    for gender, count in sorted(idcard_gender_counter.items()):
        pct = count / sum(idcard_gender_counter.values()) * 100
        label = "女" if gender == 1 else "男" if gender == 0 else "未知"
        print(f"  性别={gender} ({label}): {count} ({pct:.1f}%)")

    print(f"\n✅ 验证结果:")
    total_valid = match_counter['match'] + match_counter['mismatch']
    if total_valid > 0:
        match_rate = match_counter['match'] / total_valid * 100
        print(f"  匹配数: {match_counter['match']}")
        print(f"  不匹配数: {match_counter['mismatch']}")
        print(f"  匹配率: {match_rate:.2f}%")

    if mismatches:
        print(f"\n⚠️ 发现 {len(mismatches)} 个不匹配样本（显示前10个）:")
        for m in mismatches[:10]:
            print(f"  文件: {m['file']}")
            print(f"    base.gender={m['gender']} ({'女' if m['gender']==0 else '男'})")
            print(f"    idCard性别={m['idcard_gender']} ({'女' if m['idcard_gender']==1 else '男'})")
            print(f"    idCard: {m['idCard']}, 生日: {m.get('birthday')}")
            print()

    return match_counter['match'] > match_counter['mismatch']


if __name__ == "__main__":
    result = verify_gender_field()
    if result:
        print("\n✅ 验证通过：base.gender字段与身份证号推导一致")
    else:
        print("\n❌ 验证失败：base.gender字段与身份证号推导不一致")