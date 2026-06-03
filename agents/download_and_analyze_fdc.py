"""
批量下载并分析所有样本的FDC字段分布

目标：从0421全样本短链.txt下载所有样本，分析FDC字段枚举值分布
"""

import json
import os
import urllib.request
import time
from collections import Counter
from tqdm import tqdm


def download_json(url: str, output_dir: str = "data/all_samples") -> str:
    """下载单个JSON文件"""
    os.makedirs(output_dir, exist_ok=True)

    # 从URL提取orderId
    order_id = url.strip().split('/')[-1]
    output_file = os.path.join(output_dir, f"{order_id}.json")

    # 如果已存在，跳过
    if os.path.exists(output_file):
        return output_file

    try:
        urllib.request.urlretrieve(url.strip(), output_file)
        time.sleep(0.1)  # 避免请求过快
        return output_file
    except Exception as e:
        print(f"  ⚠️ 下载失败 {url}: {e}")
        return None


def analyze_single_file(filepath: str) -> dict:
    """分析单个文件的FDC字段"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

            # FDC可能在顶层或params下
            fdc_data = None
            if isinstance(data, dict):
                fdc_data = data.get('FDC') or data.get('params', {}).get('FDC')

            if not fdc_data or 'pinjaman' not in fdc_data:
                return None

            # 提取所有感兴趣的字段
            result = {
                'status_pinjaman': [],
                'status_pinjaman_ket': [],
                'kualitas_pinjaman': [],
                'kualitas_pinjaman_ket': [],
                'penyelesaian_w_oleh': [],
                'tipe_pinjaman': [],
                'sub_tipe_pinjaman': [],
                'pendanaan_syariah': [],
                'jenis_pengguna_ket': [],
                'id_penyelenggara': [],
                'dpd_max': []
            }

            for loan in fdc_data['pinjaman']:
                result['status_pinjaman'].append(loan.get('status_pinjaman', 'UNKNOWN'))
                result['status_pinjaman_ket'].append(loan.get('status_pinjaman_ket', 'UNKNOWN'))
                result['kualitas_pinjaman'].append(loan.get('kualitas_pinjaman', 'UNKNOWN'))
                result['kualitas_pinjaman_ket'].append(loan.get('kualitas_pinjaman_ket', 'UNKNOWN'))
                result['penyelesaian_w_oleh'].append(loan.get('penyelesaian_w_oleh', 'UNKNOWN'))
                result['tipe_pinjaman'].append(loan.get('tipe_pinjaman', 'UNKNOWN'))
                result['sub_tipe_pinjaman'].append(loan.get('sub_tipe_pinjaman', 'UNKNOWN'))
                result['pendanaan_syariah'].append(str(loan.get('pendanaan_syariah', 'UNKNOWN')))
                result['jenis_pengguna_ket'].append(loan.get('jenis_pengguna_ket', 'UNKNOWN'))
                result['id_penyelenggara'].append(loan.get('id_penyelenggara', 'UNKNOWN'))
                result['dpd_max'].append(loan.get('dpd_max', 0))

            return result

    except Exception as e:
        print(f"  ⚠️ 分析失败 {filepath}: {e}")
        return None


def main():
    print("=" * 70)
    print("批量下载并分析FDC字段分布")
    print("=" * 70)

    # Step 1: 读取短链文件
    with open('0421全样本短链.txt', 'r') as f:
        urls = [line.strip() for line in f if line.strip()]

    print(f"📂 读取到 {len(urls)} 个样本URL")

    # Step 2: 批量下载（全量）
    print(f"\n📥 开始下载 {len(urls)} 个样本...")
    downloaded_files = []

    for url in tqdm(urls, desc="下载样本"):
        filepath = download_json(url)
        if filepath:
            downloaded_files.append(filepath)

    print(f"✅ 成功下载 {len(downloaded_files)} 个样本")

    # Step 3: 分析所有文件
    print(f"\n🔍 开始分析 {len(downloaded_files)} 个文件...")

    # 累积计数器
    total_counters = {
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
        'dpd_max': []
    }

    total_loans = 0
    success_count = 0

    for filepath in tqdm(downloaded_files, desc="分析文件"):
        result = analyze_single_file(filepath)
        if result:
            success_count += 1
            for field in ['status_pinjaman', 'status_pinjaman_ket', 'kualitas_pinjaman',
                          'kualitas_pinjaman_ket', 'penyelesaian_w_oleh', 'tipe_pinjaman',
                          'sub_tipe_pinjaman', 'pendanaan_syariah', 'jenis_pengguna_ket',
                          'id_penyelenggara']:
                total_counters[field].update(result[field])

            total_counters['dpd_max'].extend(result['dpd_max'])
            total_loans += len(result['status_pinjaman'])

    print(f"\n✅ 成功分析 {success_count} 个文件，共 {total_loans} 条贷款记录")

    # Step 4: 生成统计报告
    report = {
        "total_samples": len(downloaded_files),
        "total_loans": total_loans,
        "field_distributions": {
            "status_pinjaman": dict(total_counters['status_pinjaman'].most_common()),
            "status_pinjaman_ket": dict(total_counters['status_pinjaman_ket'].most_common()),
            "kualitas_pinjaman": dict(total_counters['kualitas_pinjaman'].most_common()),
            "kualitas_pinjaman_ket": dict(total_counters['kualitas_pinjaman_ket'].most_common()),
            "penyelesaian_w_oleh": dict(total_counters['penyelesaian_w_oleh'].most_common()),
            "tipe_pinjaman": dict(total_counters['tipe_pinjaman'].most_common()),
            "sub_tipe_pinjaman": dict(total_counters['sub_tipe_pinjaman'].most_common()),
            "pendanaan_syariah": dict(total_counters['pendanaan_syariah'].most_common()),
            "jenis_pengguna_ket": dict(total_counters['jenis_pengguna_ket'].most_common()),
            "id_penyelenggara": dict(total_counters['id_penyelenggara'].most_common(50)),  # Top 50
            "dpd_max_stats": {
                "min": min(total_counters['dpd_max']) if total_counters['dpd_max'] else 0,
                "max": max(total_counters['dpd_max']) if total_counters['dpd_max'] else 0,
                "mean": sum(total_counters['dpd_max']) / len(total_counters['dpd_max']) if total_counters['dpd_max'] else 0,
                "zero_count": sum(1 for x in total_counters['dpd_max'] if x == 0),
                "positive_count": sum(1 for x in total_counters['dpd_max'] if x > 0)
            }
        }
    }

    # Step 5: 保存结果
    output_file = "outputs/feature_design/stepwise/fdc_field_distributions_full.json"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n💾 结果已保存到: {output_file}")

    # Step 6: 打印摘要
    print("\n" + "=" * 70)
    print("分析结果摘要（全量样本）")
    print("=" * 70)

    print(f"\n📊 样本规模:")
    print(f"  下载样本数: {len(downloaded_files)} / {len(urls)}")
    print(f"  成功分析数: {success_count}")
    print(f"  总贷款记录: {total_loans}")

    print(f"\n📊 关键字段枚举值:")
    for field in ['status_pinjaman', 'kualitas_pinjaman', 'tipe_pinjaman',
                  'sub_tipe_pinjaman', 'pendanaan_syariah']:
        values = list(report['field_distributions'][field].items())[:10]
        print(f"  {field}: {values}")

    print(f"\n📊 DPD分布:")
    dpd_stats = report['field_distributions']['dpd_max_stats']
    print(f"  范围: {dpd_stats['min']} - {dpd_stats['max']}")
    print(f"  均值: {dpd_stats['mean']:.2f}")
    print(f"  DPD=0的贷款数: {dpd_stats['zero_count']}")
    print(f"  DPD>0的贷款数: {dpd_stats['positive_count']}")

    print(f"\n📊 机构ID统计:")
    print(f"  唯一机构数: {len(report['field_distributions']['id_penyelenggara'])}")
    print(f"  Top 10: {list(report['field_distributions']['id_penyelenggara'].items())[:10]}")

    print("\n✅ 分析完成！")


if __name__ == "__main__":
    main()
