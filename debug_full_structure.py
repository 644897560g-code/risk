"""
检查完整JSON结构 - 找出FDC数据实际位置
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
    print("="*80)
    print("完整JSON顶层键:")
    print("="*80)
    print(list(data.keys()))

    print("\n\n检查params键:")
    params = data.get('params', {})
    print(f"params键列表: {list(params.keys())}")

    print("\n\n检查FDC是否在params中:")
    if 'FDC' in params:
        print("✅ FDC在params中")
        fdc = params['FDC']
        print(f"FDC键: {list(fdc.keys())}")
    else:
        print("❌ FDC不在params中")

    print("\n\n检查data中是否有FDC:")
    if 'FDC' in data:
        print("✅ FDC在data根级别")
        fdc = data['FDC']
        print(f"FDC键: {list(fdc.keys())}")
        history = fdc.get('history_inquiry', {})
        stats = history.get('statistic', {})
        print(f"statistics键: {list(stats.keys())}")
        pinjaman = fdc.get('pinjaman', [])
        print(f"pinjaman数量: {len(pinjaman)}")
    else:
        print("❌ FDC不在data根级别")

    print("\n\n所有顶层键的值类型:")
    for key in data.keys():
        val = data[key]
        if isinstance(val, dict):
            print(f"  {key}: dict (keys: {list(val.keys())[:5]})")
        elif isinstance(val, list):
            print(f"  {key}: list (len: {len(val)})")
        else:
            print(f"  {key}: {type(val).__name__} = {str(val)[:100]}")
