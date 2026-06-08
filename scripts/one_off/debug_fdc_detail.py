"""
调试FDC实际数据结构 - 详细检查
"""

import sys
import os
import json
sys.path.insert(0, os.path.dirname(__file__))

from data.data_loader import ShortLinkFetcher

# 获取1条数据
fetcher = ShortLinkFetcher()
link = "https://ng-fenqi-prod-1320687172.oss-us-west-1.aliyuncs.com/Apply/order-formatfile/id002luzt202603090951432723072"

data = fetcher.fetch_json(link)

if data:
    fdc = data.get('params', {}).get('FDC', {})

    print("="*80)
    print("FDC详细结构")
    print("="*80)

    history = fdc.get('history_inquiry', {})
    print(f"\nhistory_inquiry 类型: {type(history)}")
    print(f"history_inquiry 键: {list(history.keys()) if isinstance(history, dict) else 'NOT A DICT'}")
    print(f"history_inquiry 内容: {json.dumps(history, ensure_ascii=False, indent=2)[:500]}")

    stats = history.get('statistic', {}) if isinstance(history, dict) else {}
    print(f"\nstatistic 类型: {type(stats)}")
    print(f"statistic 内容: {json.dumps(stats, ensure_ascii=False, indent=2)[:500]}")

    pinjaman = fdc.get('pinjaman', [])
    print(f"\npinjaman 类型: {type(pinjaman)}")
    print(f"pinjaman 数量: {len(pinjaman)}")
    if pinjaman and isinstance(pinjaman, list) and len(pinjaman) > 0:
        print(f"第一条pinjaman 类型: {type(pinjaman[0])}")
        print(f"第一条pinjaman 键: {list(pinjaman[0].keys())[:10] if isinstance(pinjaman[0], dict) else 'NOT A DICT'}")

    platforms = fdc.get('platform_aktif', {})
    print(f"\nplatform_aktif 类型: {type(platforms)}")
    print(f"platform_aktif 内容: {json.dumps(platforms, ensure_ascii=False, indent=2)[:500]}")
