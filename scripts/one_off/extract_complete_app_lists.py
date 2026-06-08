"""
Extract complete application lists from all 2914 samples

This script processes ALL short links to extract complete app lists for:
- Good customers (is_overdue=0): 626 customers
- Bad customers (is_overdue=1): 1646 customers
- Common apps (installed by both)
"""

import sys
import os
import json
import pandas as pd
from collections import defaultdict
import time

sys.path.insert(0, os.path.dirname(__file__))

from data.data_loader import DataLoader, ShortLinkFetcher

def main():
    print("="*80)
    print("Extracting complete application lists from all samples")
    print("="*80)

    # Load data
    print("\nStep 1: Loading data...")
    loader = DataLoader()
    fetcher = ShortLinkFetcher()

    short_links = loader.load_short_links()
    model_samples = loader.load_model_samples()

    print(f"   Short links: {len(short_links)}")
    print(f"   Model samples: {len(model_samples)}")

    # Separate good/bad customers
    good_customers = model_samples[model_samples['is_overdue'] == 0]
    bad_customers = model_samples[model_samples['is_overdue'] == 1]

    good_order_ids = set(good_customers['source_order_no'].tolist())
    bad_order_ids = set(bad_customers['source_order_no'].tolist())

    print(f"   Good customers: {len(good_order_ids)}")
    print(f"   Bad customers: {len(bad_order_ids)}")

    # Process all short links
    print(f"\nStep 2: Processing {len(short_links)} short links (this will take 10-30 minutes)...")

    # Application counts
    good_apps = defaultdict(int)
    bad_apps = defaultdict(int)

    success_count = 0
    fail_count = 0

    for i, link in enumerate(short_links):
        try:
            data = fetcher.fetch_json(link)
            if not data:
                fail_count += 1
                continue

            success_count += 1
            order_id = data.get('orderId', '')
            app_list = data.get('params', {}).get('appList', [])

            for app in app_list:
                package = app.get('packageX', '')
                if not package:
                    continue

                if order_id in good_order_ids:
                    good_apps[package] += 1
                elif order_id in bad_order_ids:
                    bad_apps[package] += 1

        except Exception as e:
            fail_count += 1
            # print(f"   Error processing {link}: {e}")

        # Progress update
        if (i + 1) % 100 == 0:
            elapsed = time.time()
            print(f"   Progress: {i+1}/{len(short_links)} ({(i+1)/len(short_links)*100:.1f}%) - "
                  f"Success: {success_count}, Failed: {fail_count}")

    print(f"\n   Final: Success={success_count}, Failed={fail_count}")

    # Calculate unique apps
    print(f"\nStep 3: Calculating unique applications...")

    good_only = {k: v for k, v in good_apps.items() if k not in bad_apps}
    bad_only = {k: v for k, v in bad_apps.items() if k not in good_apps}
    common = {k: v for k, v in good_apps.items() if k in bad_apps}

    print(f"   Good customer unique apps: {len(good_only)}")
    print(f"   Bad customer unique apps: {len(bad_only)}")
    print(f"   Common apps: {len(common)}")
    print(f"   Total unique apps: {len(good_only) + len(bad_only) + len(common)}")

    # Save complete lists
    print(f"\nStep 4: Saving complete application lists...")

    # Good customer only apps - sorted by installation count
    good_only_records = []
    for app, count in sorted(good_only.items(), key=lambda x: x[1], reverse=True):
        good_only_records.append({
            'app': app,
            'good_count': count,
            'bad_count': 0,
            'total_count': count,
            'good_rate_pct': round(count / len(good_order_ids) * 100, 4) if len(good_order_ids) > 0 else 0,
            'bad_rate_pct': 0.0,
            'risk_ratio': 0.0
        })

    good_only_df = pd.DataFrame(good_only_records)
    good_only_df.to_csv('outputs/app_analysis/good_customer_apps_complete.csv', index=False)
    print(f"   ✓ Good customer apps saved: {len(good_only_df)} apps")

    # Bad customer only apps - sorted by installation count
    bad_only_records = []
    for app, count in sorted(bad_only.items(), key=lambda x: x[1], reverse=True):
        bad_only_records.append({
            'app': app,
            'good_count': 0,
            'bad_count': count,
            'total_count': count,
            'good_rate_pct': 0.0,
            'bad_rate_pct': round(count / len(bad_order_ids) * 100, 4) if len(bad_order_ids) > 0 else 0,
            'risk_ratio': 999.99
        })

    bad_only_df = pd.DataFrame(bad_only_records)
    bad_only_df.to_csv('outputs/app_analysis/bad_customer_apps_complete.csv', index=False)
    print(f"   ✓ Bad customer apps saved: {len(bad_only_df)} apps")

    # Common apps - sorted by total installation count
    common_records = []
    for app in common.keys():
        g_count = good_apps[app]
        b_count = bad_apps[app]
        total = g_count + b_count
        g_rate = round(g_count / len(good_order_ids) * 100, 4) if len(good_order_ids) > 0 else 0
        b_rate = round(b_count / len(bad_order_ids) * 100, 4) if len(bad_order_ids) > 0 else 0
        ratio = round(b_rate / g_rate, 2) if g_rate > 0 else 999.99

        common_records.append({
            'app': app,
            'good_count': g_count,
            'bad_count': b_count,
            'total_count': total,
            'good_rate_pct': g_rate,
            'bad_rate_pct': b_rate,
            'risk_ratio': ratio
        })

    common_df = pd.DataFrame(common_records)
    common_df = common_df.sort_values('total_count', ascending=False)
    common_df.to_csv('outputs/app_analysis/common_apps_complete.csv', index=False)
    print(f"   ✓ Common apps saved: {len(common_df)} apps")

    # Summary
    print("\n" + "="*80)
    print("Complete application list extraction finished!")
    print("="*80)
    print(f"\nFiles saved to outputs/app_analysis/:")
    print(f"  - good_customer_apps_complete.csv: {len(good_only_df)} apps")
    print(f"  - bad_customer_apps_complete.csv: {len(bad_only_df)} apps")
    print(f"  - common_apps_complete.csv: {len(common_df)} apps")

    # Update summary JSON
    summary_path = 'outputs/app_analysis/app_analysis_summary.json'
    with open(summary_path, 'r', encoding='utf-8') as f:
        summary = json.load(f)

    summary['unique_apps'] = {
        'total': len(good_only) + len(bad_only) + len(common),
        'good_only': len(good_only),
        'bad_only': len(bad_only),
        'common': len(common)
    }

    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\nSummary JSON updated: {summary_path}")


if __name__ == '__main__':
    main()
