"""
临时脚本：测试阿里云OSS取数情况
- 读取 0421全样本短链.txt
- 取前50条URL，timeout=30s
- 统计成功率、耗时、FDC数据覆盖率
"""
import json
import time
import requests
import sys
from datetime import datetime

SHORT_URL_FILE = '0421全样本短链.txt'
SAMPLE_SIZE = 50
TIMEOUT = 30

def main():
    # 1. 加载URL
    with open(SHORT_URL_FILE, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    print(f"总URL数: {len(urls)}")
    print(f"测试前{SAMPLE_SIZE}条, timeout={TIMEOUT}s\n")

    # 2. 逐条测试
    success = 0
    fail = 0
    fdc_count = 0
    fdc_empty = 0
    has_history_inquiry = 0
    has_pinjaman = 0
    total_time = 0
    details = []

    for i, url in enumerate(urls[:SAMPLE_SIZE]):
        start = time.time()
        try:
            resp = requests.get(url, timeout=TIMEOUT)
            elapsed = time.time() - start
            total_time += elapsed

            if resp.status_code == 200:
                data = resp.json()
                order_id = data.get('orderId', f'第{i+1}条')
                params = data.get('params', {})
                base = params.get('base', {})
                app_list = params.get('appList', [])
                fdc = params.get('FDC', {})  # FDC 在 params 下，不是 data.FDC

                # FDC分析
                has_fdc = bool(fdc)
                hi = fdc.get('history_inquiry', []) if isinstance(fdc, dict) else []
                pj = fdc.get('pinjaman', []) if isinstance(fdc, dict) else []

                if has_fdc:
                    fdc_count += 1
                else:
                    fdc_empty += 1
                if isinstance(hi, list) and len(hi) > 0:
                    has_history_inquiry += 1
                if isinstance(pj, list) and len(pj) > 0:
                    has_pinjaman += 1

                # base字段
                base_fields = list(base.keys()) if base else []

                status = "✅"
                detail_parts = [
                    f"FDC={'有' if has_fdc else '无'}",
                    f"history_inquiry={len(hi) if isinstance(hi, list) else 0}条",
                    f"pinjaman={len(pj) if isinstance(pj, list) else 0}条",
                    f"appList={len(app_list)}个",
                    f"base字段={len(base_fields)}个",
                    f"耗时={elapsed:.1f}s"
                ]
                detail = f"  {status} [{i+1}/{SAMPLE_SIZE}] {order_id[:40]:40s} | {' | '.join(detail_parts)}"
                details.append(detail)
                success += 1
            else:
                elapsed = time.time() - start
                total_time += elapsed
                detail = f"  ❌ [{i+1}/{SAMPLE_SIZE}] HTTP {resp.status_code} | 耗时={elapsed:.1f}s"
                details.append(detail)
                fail += 1

        except requests.Timeout:
            elapsed = time.time() - start
            total_time += elapsed
            detail = f"  ⏰ [{i+1}/{SAMPLE_SIZE}] 超时 | 耗时={elapsed:.1f}s"
            details.append(detail)
            fail += 1
        except Exception as e:
            elapsed = time.time() - start
            total_time += elapsed
            detail = f"  ❌ [{i+1}/{SAMPLE_SIZE}] 异常: {str(e)[:60]} | 耗时={elapsed:.1f}s"
            details.append(detail)
            fail += 1

        if (i + 1) % 10 == 0:
            print(f"  进度: {i+1}/{SAMPLE_SIZE}...")

    # 3. 汇总
    print("\n" + "=" * 70)
    print("测试结果汇总")
    print("=" * 70)
    print(f"\n总请求: {SAMPLE_SIZE}")
    print(f"成功: {success} ({100*success/SAMPLE_SIZE:.1f}%)")
    print(f"失败: {fail} ({100*fail/SAMPLE_SIZE:.1f}%)")
    print(f"总耗时: {total_time:.1f}s")
    print(f"平均耗时: {total_time/SAMPLE_SIZE:.1f}s (含失败)")
    if success > 0:
        avg_success = total_time / success if success > 0 else 0
        print(f"成功平均耗时: {total_time/success:.1f}s")

    print(f"\n--- FDC数据覆盖 ---")
    print(f"有FDC数据: {fdc_count} ({100*fdc_count/SAMPLE_SIZE:.1f}%)")
    print(f"FDC为空: {fdc_empty} ({100*fdc_empty/SAMPLE_SIZE:.1f}%)")
    print(f"有history_inquiry: {has_history_inquiry}")
    print(f"有pinjaman: {has_pinjaman}")

    print(f"\n--- 详细 ---")
    for d in details:
        print(d)


if __name__ == '__main__':
    main()
