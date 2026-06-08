"""
FDC重要字段枚举值分布分析

目标：分析FDC数据中关键字段的枚举值分布，为特征模板生成提供准确的数据字典

分析的字段：
1. status_pinjaman - 贷款状态
2. status_pinjaman_ket - 贷款状态描述
3. kualitas_pinjaman - 贷款质量代码
4. kualitas_pinjaman_ket - 贷款质量描述
5. penyelesaian_w_oleh - 违约解决方式
6. dpd_max - 最大逾期天数（统计分布）
7. id_penyelenggara - 机构ID（需要分类）
8. tipe_pinjaman - 贷款类型
9. sub_tipe_pinjaman - 子贷款类型
10. pendanaan_syariah - 是否伊斯兰金融
11. jenis_pengguna_ket - 用户类型描述

输出：JSON格式的字段分布统计，供Phase 3使用
"""

import json
import os
import glob
from collections import Counter, defaultdict
from tqdm import tqdm


def load_sample_data(data_dir: str = ".") -> list:
    """加载样本数据"""
    # 直接查找data_dir目录下的所有JSON文件
    json_files = glob.glob(os.path.join(data_dir, "*.json"))

    # 如果没有，查找子目录
    if not json_files:
        json_files = glob.glob(os.path.join(data_dir, "**/*.json"), recursive=True)

    if not json_files:
        print(f"❌ 在 {data_dir} 目录下未找到JSON文件")
        return []

    print(f"📂 找到 {len(json_files)} 个JSON文件")

    samples = []
    for json_file in json_files:  # 处理所有样本
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # FDC可能在顶层或params下
                fdc_data = None
                if isinstance(data, dict):
                    fdc_data = data.get('FDC') or data.get('params', {}).get('FDC')

                if fdc_data and 'pinjaman' in fdc_data:
                    samples.append(fdc_data)
        except Exception as e:
            print(f"  ⚠️ 读取文件 {json_file} 失败: {e}")

    print(f"✅ 成功加载 {len(samples)} 个包含FDC数据的样本")
    return samples


def analyze_fdc_fields(samples: list) -> dict:
    """分析FDC字段分布"""

    # 初始化计数器
    field_counters = {
        'status_pinjaman': Counter(),
        'status_pinjaman_ket': Counter(),
        'kualitas_pinjaman': Counter(),
        'kualitas_pinjaman_ket': Counter(),
        'penyelesaian_w_oleh': Counter(),
        'tipe_pinjaman': Counter(),
        'sub_tipe_pinjaman': Counter(),
        'pendanaan_syariah': Counter(),
        'jenis_pengguna_ket': Counter(),
        'id_penyelenggara': Counter(),
        'dpd_max_stats': {
            'min': float('inf'),
            'max': float('-inf'),
            'mean': 0,
            'sum': 0,
            'count': 0,
            'zero_count': 0,
            'positive_count': 0
        }
    }

    total_loans = 0

    print("\n🔍 开始分析FDC字段分布...")

    for fdc_data in tqdm(samples, desc="分析样本"):
        # samples现在直接是FDC数据，不是完整订单
        pinjaman_list = fdc_data.get('pinjaman', [])

        for loan in pinjaman_list:
            total_loans += 1

            # 统计枚举字段
            for field in ['status_pinjaman', 'status_pinjaman_ket', 'kualitas_pinjaman',
                          'kualitas_pinjaman_ket', 'penyelesaian_w_oleh', 'tipe_pinjaman',
                          'sub_tipe_pinjaman', 'jenis_pengguna_ket']:
                value = loan.get(field, 'UNKNOWN')
                field_counters[field][value] += 1

            # 统计布尔字段
            pendanaan_syariah = loan.get('pendanaan_syariah', False)
            field_counters['pendanaan_syariah'][str(pendanaan_syariah)] += 1

            # 统计机构ID
            id_penyelenggara = loan.get('id_penyelenggara', 'UNKNOWN')
            field_counters['id_penyelenggara'][id_penyelenggara] += 1

            # 统计DPD分布
            dpd_max = loan.get('dpd_max', 0)
            field_counters['dpd_max_stats']['min'] = min(field_counters['dpd_max_stats']['min'], dpd_max)
            field_counters['dpd_max_stats']['max'] = max(field_counters['dpd_max_stats']['max'], dpd_max)
            field_counters['dpd_max_stats']['sum'] += dpd_max
            field_counters['dpd_max_stats']['count'] += 1
            if dpd_max == 0:
                field_counters['dpd_max_stats']['zero_count'] += 1
            else:
                field_counters['dpd_max_stats']['positive_count'] += 1

    # 计算DPD均值
    if field_counters['dpd_max_stats']['count'] > 0:
        field_counters['dpd_max_stats']['mean'] = (
            field_counters['dpd_max_stats']['sum'] / field_counters['dpd_max_stats']['count']
        )

    # 转换Counter为dict（方便JSON序列化）
    result = {}
    for field, counter in field_counters.items():
        if field == 'dpd_max_stats':
            result[field] = counter
        else:
            result[field] = dict(counter.most_common())

    result['total_loans'] = total_loans
    result['total_samples'] = len(samples)

    print(f"\n✅ 分析完成！共处理 {total_loans} 条贷款记录")

    return result


def generate_data_dictionary(analysis_result: dict) -> dict:
    """生成数据字典（供Phase 3使用）"""

    data_dict = {
        "fdc_field_distributions": {
            "status_pinjaman": {
                "description": "贷款状态代码",
                "values": analysis_result.get('status_pinjaman', {}),
                "example_values": list(analysis_result.get('status_pinjaman', {}).keys())[:5]
            },
            "status_pinjaman_ket": {
                "description": "贷款状态描述",
                "values": analysis_result.get('status_pinjaman_ket', {}),
                "example_values": list(analysis_result.get('status_pinjaman_ket', {}).keys())[:5]
            },
            "kualitas_pinjaman": {
                "description": "贷款质量代码",
                "values": analysis_result.get('kualitas_pinjaman', {}),
                "example_values": list(analysis_result.get('kualitas_pinjaman', {}).keys())[:5]
            },
            "kualitas_pinjaman_ket": {
                "description": "贷款质量描述",
                "values": analysis_result.get('kualitas_pinjaman_ket', {}),
                "example_values": list(analysis_result.get('kualitas_pinjaman_ket', {}).keys())[:5]
            },
            "penyelesaian_w_oleh": {
                "description": "违约解决方式",
                "values": analysis_result.get('penyelesaian_w_oleh', {}),
                "example_values": list(analysis_result.get('penyelesaian_w_oleh', {}).keys())[:5]
            },
            "tipe_pinjaman": {
                "description": "贷款类型",
                "values": analysis_result.get('tipe_pinjaman', {}),
                "example_values": list(analysis_result.get('tipe_pinjaman', {}).keys())[:5]
            },
            "sub_tipe_pinjaman": {
                "description": "子贷款类型",
                "values": analysis_result.get('sub_tipe_pinjaman', {}),
                "example_values": list(analysis_result.get('sub_tipe_pinjaman', {}).keys())[:5]
            },
            "pendanaan_syariah": {
                "description": "是否伊斯兰金融",
                "values": analysis_result.get('pendanaan_syariah', {}),
                "example_values": ["true", "false"]
            },
            "jenis_pengguna_ket": {
                "description": "用户类型描述",
                "values": analysis_result.get('jenis_pengguna_ket', {}),
                "example_values": list(analysis_result.get('jenis_pengguna_ket', {}).keys())[:5]
            },
            "dpd_max_stats": {
                "description": "最大逾期天数分布",
                "stats": analysis_result.get('dpd_max_stats', {}),
                "interpretation": f"DPD范围: {analysis_result.get('dpd_max_stats', {}).get('min', 0)} - {analysis_result.get('dpd_max_stats', {}).get('max', 0)}, 均值: {analysis_result.get('dpd_max_stats', {}).get('mean', 0):.2f}"
            },
            "id_penyelenggara": {
                "description": "机构ID列表（需要业务分类）",
                "values": analysis_result.get('id_penyelenggara', {}),
                "unique_count": len(analysis_result.get('id_penyelenggara', {})),
                "top_20": dict(list(analysis_result.get('id_penyelenggara', {}).items())[:20])
            }
        },
        "usage_guidance": {
            "instruction": "Phase 3生成模板时，parameter_space的值必须基于上述枚举值",
            "examples": {
                "status_types": "应使用: ['O', 'L', 'C', 'W']，而不是 ['approved', 'rejected', 'pending']",
                "loan_quality": "应使用: ['1', '2']，对应 ['Lancar', 'Dalam Perhatian']",
                "institution_types": "需要基于 id_penyelenggara 定义分类规则（当前未配置）"
            }
        }
    }

    return data_dict


def main():
    print("=" * 70)
    print("FDC重要字段枚举值分布分析")
    print("=" * 70)

    # Step 1: 加载样本数据
    import sys
    sample_dir = sys.argv[1] if len(sys.argv) > 1 else "data/all_samples"
    output_file_path = sys.argv[2] if len(sys.argv) > 2 else "outputs/feature_design/stepwise/fdc_field_distributions.json"

    samples = load_sample_data(sample_dir)

    if not samples:
        print("❌ 未找到样本数据，退出")
        return

    # Step 2: 分析字段分布
    analysis_result = analyze_fdc_fields(samples)

    # Step 3: 生成数据字典
    data_dict = generate_data_dictionary(analysis_result)

    # Step 4: 保存结果
    output_dir = "outputs/feature_design/stepwise"
    os.makedirs(output_dir, exist_ok=True)

    output_file = output_file_path
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data_dict, f, ensure_ascii=False, indent=2)

    print(f"\n💾 结果已保存到: {output_file}")

    # Step 5: 打印摘要
    print("\n" + "=" * 70)
    print("分析结果摘要")
    print("=" * 70)

    print(f"\n📊 样本信息:")
    print(f"  总样本数: {analysis_result['total_samples']}")
    print(f"  总贷款记录数: {analysis_result['total_loans']}")

    print(f"\n📊 关键字段枚举值:")
    for field in ['status_pinjaman', 'kualitas_pinjaman', 'tipe_pinjaman',
                  'sub_tipe_pinjaman', 'pendanaan_syariah']:
        values = list(data_dict['fdc_field_distributions'][field]['values'].keys())
        print(f"  {field}: {values}")

    print(f"\n📊 DPD分布:")
    dpd_stats = data_dict['fdc_field_distributions']['dpd_max_stats']['stats']
    print(f"  范围: {dpd_stats['min']} - {dpd_stats['max']}")
    print(f"  均值: {dpd_stats['mean']:.2f}")
    print(f"  DPD=0的贷款数: {dpd_stats['zero_count']}")
    print(f"  DPD>0的贷款数: {dpd_stats['positive_count']}")

    print(f"\n📊 机构ID统计:")
    print(f"  唯一机构数: {data_dict['fdc_field_distributions']['id_penyelenggara']['unique_count']}")
    print(f"  Top 5机构: {list(data_dict['fdc_field_distributions']['id_penyelenggara']['values'].items())[:5]}")

    print("\n✅ 分析完成！请在Phase 3中使用此数据字典约束模板生成")


if __name__ == "__main__":
    main()
