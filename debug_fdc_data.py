"""
调试FDC数据结构 - 检查实际字段名和数据值
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

# 读取样例JSON文件
sample_file = "id002luzt202603090951432723072"

with open(sample_file, 'r') as f:
    data = json.load(f)

fdc = data.get('FDC', {})
print("="*80)
print("FDC数据结构分析")
print("="*80)

# 检查history_inquiry
history = fdc.get('history_inquiry', {})
stats = history.get('statistic', {})

print("\n1. history_inquiry.statistic:")
print(f"   类型: {type(stats)}")
print(f"   键: {list(stats.keys())}")
print(f"   值: {stats}")

# 检查pinjaman
pinjaman = fdc.get('pinjaman', [])
print(f"\n2. pinjaman:")
print(f"   类型: {type(pinjaman)}")
print(f"   数量: {len(pinjaman)}")
if pinjaman:
    print(f"   第一条记录的键: {list(pinjaman[0].keys())[:10]}")
    print(f"   示例 - sisa_pinjaman_berjalan: {pinjaman[0].get('sisa_pinjaman_berjalan')}")
    print(f"   示例 - dpd_max: {pinjaman[0].get('dpd_max')}")

# 检查platform_aktif
platforms = fdc.get('platform_aktif', {})
print(f"\n3. platform_aktif:")
print(f"   类型: {type(platforms)}")
print(f"   键: {list(platforms.keys())}")
print(f"   值: {platforms}")

# 模拟统计数据
print("\n4. 模拟统计计算:")
query_3days = [stats.get('3_hari', 0)]
query_7days = [stats.get('7_hari', 0)]
query_30days = [stats.get('30_hari', 0)]

print(f"   3天查询: {query_3days}")
print(f"   7天查询: {query_7days}")
print(f"   30天查询: {query_30days}")

loan_counts = [len(pinjaman)]
outstanding = sum(p.get('sisa_pinjaman_berjalan', 0) for p in pinjaman)
print(f"   贷款笔数: {loan_counts}")
print(f"   在贷余额总和: {outstanding}")

dpds = [p.get('dpd_max', 0) for p in pinjaman]
print(f"   DPD列表: {dpds[:5]}...")
print(f"   最大DPD: {max(dpds) if dpds else 0}")

print("\n" + "="*80)
print("检查完成")
print("="*80)
