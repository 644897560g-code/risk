"""
调试实际从短链加载的FDC数据
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from data.data_loader import ShortLinkFetcher

# 获取前5条数据
fetcher = ShortLinkFetcher()
links = [
    "https://ng-fenqi-prod-1320687172.oss-us-west-1.aliyuncs.com/Apply/order-formatfile/id002luzt202603090951432723072",
    "https://ng-fenqi-prod-1320687172.oss-us-west-1.aliyuncs.com/Apply/order-formatfile/id002trjk202603181536163973706",
    "https://ng-fenqi-prod-1320687172.oss-us-west-1.aliyuncs.com/Apply/order-formatfile/id002yreq202604031849015981723"
]

print("="*80)
print("检查短链实际FDC数据结构")
print("="*80)

for i, link in enumerate(links[:3]):
    print(f"\n样本 {i+1}: {link.split('/')[-1]}")
    data = fetcher.fetch_json(link)

    if data:
        fdc = data.get('FDC', {})

        # 检查history_inquiry
        history = fdc.get('history_inquiry', {})
        stats = history.get('statistic', {})
        print(f"  history_inquiry.statistic 键: {list(stats.keys()) if stats else 'EMPTY'}")
        if stats:
            print(f"    值: {stats}")

        # 检查pinjaman
        pinjaman = fdc.get('pinjaman', [])
        print(f"  pinjaman 数量: {len(pinjaman)}")
        if pinjaman and len(pinjaman) > 0:
            print(f"    第一条 - sisa_pinjaman_berjalan: {pinjaman[0].get('sisa_pinjaman_berjalan')}")
            print(f"    第一条 - dpd_max: {pinjaman[0].get('dpd_max')}")
            print(f"    第一条 - 键(前10): {list(pinjaman[0].keys())[:10]}")

        # 检查platform_aktif
        platforms = fdc.get('platform_aktif', {})
        print(f"  platform_aktif 键: {list(platforms.keys()) if platforms else 'EMPTY'}")
        if platforms:
            print(f"    值: {platforms}")
    else:
        print("  获取数据失败")

print("\n" + "="*80)
print("检查完成")
print("="*80)
