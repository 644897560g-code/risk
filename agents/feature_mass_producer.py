"""
Mass Feature Producer — 确定性批量特征生成引擎

绕过LLM的瓶颈，直接枚举所有有效参数组合，生成完整的
FeatureCalculator类代码。支持T010-T012的参考分布注入。

使用方法：
    from agents.feature_mass_producer import produce_all_features
    
    # 生成代码（不带参考分布）
    code = produce_all_features()

    # 生成代码（带参考分布，T010-T012生效）
    refs = {"salary_distribution": [...], ...}
    code = produce_all_features(ref_distributions=refs)
"""

import json
import math
import os
import sys
from typing import Dict, List, Tuple, Optional

import numpy as np

# ============================================================
# PARAM_COMBOS — 完整枚举所有模板的确定性参数组合
# ============================================================

# 可用窗口
WINDOWS_SHORT = [3, 7, 15]
WINDOWS_MEDIUM = [30, 60, 90]
WINDOWS_LONG = [180, 360]
WINDOWS_ALL = [7, 15, 30, 60, 90, 180, 360]

# fdc_pinjaman 有效 cond 值
FDC_PINJAMAN_CONDS = [
    (None, ""),                                          # 全部
    ('status_pinjaman', 'O'),                            # 未结清(进行中)
    ('status_pinjaman', 'L'),                            # 已结清
    ('status_pinjaman', 'W'),                            # 核销
    ('status_pinjaman', 'F'),                            # 已完成
    ('kualitas_pinjaman', '1'),                          # 正常
    ('kualitas_pinjaman', '3'),                          # 应关注
    ('kualitas_pinjaman', '5'),                          # 坏账
    ('tipe_pinjaman', 'Multiguna'),                      # 多用途贷款
    ('tipe_pinjaman', 'Produktif'),                      # 生产性贷款
    ('pendanaan_syariah', True),                         # 伊斯兰金融
    ('pendanaan_syariah', False),                        # 非伊斯兰金融
]

# applist 类别分组（用于 T004 proportion_by_category）
APPLIST_CATEGORY_GROUPS = [
    (['gambling'], "gambling"),
    (['cash_loan'], "cashloan"),
    (['fintech_lending'], "finlending"),
    (['fake_gps'], "fakegps"),
    (['clone_app'], "cloneapp"),
    (['banking'], "banking"),
    (['ewallet'], "ewallet"),
    (['cash_loan', 'fintech_lending'], "loanapps"),
    (['gambling', 'cash_loan', 'fintech_lending'], "highrisk"),
    (['shopping', 'food_delivery'], "consume"),
]

# fdc_pinjaman target_cond 组合（用于 T004 proportion）
FDC_PROP_TARGET_CONDS = [
    ({'kualitas_pinjaman': '1'}, "kualitas1"),
    ({'kualitas_pinjaman': '3'}, "kualitas3"),
    ({'kualitas_pinjaman': '5'}, "kualitas5"),
    ({'status_pinjaman': 'O'}, "statusO"),
    ({'status_pinjaman': 'L'}, "statusL"),
    ({'tipe_pinjaman': 'Multiguna'}, "multiguna"),
    ({'tipe_pinjaman': 'Produktif'}, "produktif"),
    ({'pendanaan_syariah': True}, "syariah"),
    ({'pendanaan_syariah': False}, "nonsyariah"),
]


def _build_param_combos() -> Dict[str, List[Dict]]:
    """构建所有模板的参数组合"""
    combos = {}

    # ========== T001: count ==========
    t001 = []
    # fdc_inquiry: 6 windows (预聚合，不支持cond)
    for w in [3, 7, 15, 30, 90, 180]:
        t001.append({'source': 'fdc_inquiry', 'window': w})
    # applist: 6 windows
    for w in WINDOWS_ALL:
        t001.append({'source': 'applist', 'window': w})
    # fdc_pinjaman: 12 conds x 6 windows
    for cond_key, cond_val in FDC_PINJAMAN_CONDS:
        cond = {cond_key: cond_val} if cond_key else None
        suffix = f"_{cond_key}_{cond_val}" if cond_key else ""
        for w in WINDOWS_ALL:
            d = {'source': 'fdc_pinjaman', 'window': w}
            if cond:
                d['cond'] = cond
            t001.append(d)
    combos['T001'] = t001  # 6 + 6 + 72 = 84

    # ---- T001 extensions: 360d windows + kualitas=2 cond ----
    # 360d for fdc_inquiry and applist
    t001.append({'source': 'fdc_inquiry', 'window': 360})
    t001.append({'source': 'applist', 'window': 360})
    # 360d for fdc_pinjaman (no cond)
    t001.append({'source': 'fdc_pinjaman', 'window': 360})
    # fdc_pinjaman kualitas=2 cond across all windows
    for w in WINDOWS_ALL:
        t001.append({'source': 'fdc_pinjaman', 'window': w, 'cond': {'kualitas_pinjaman': '2'}})
    # 360d for fdc_pinjaman kualitas=2
    t001.append({'source': 'fdc_pinjaman', 'window': 360, 'cond': {'kualitas_pinjaman': '2'}})

    # ========== T002: distinct_count ==========
    t002 = []
    # fdc_inquiry.hit_by: 6 windows
    for w in WINDOWS_ALL:
        t002.append({'source': 'fdc_inquiry', 'dedup_field': 'hit_by', 'window': w})
    # fdc_pinjaman.id_penyelenggara: 4 windows
    for w in [30, 60, 90, 180]:
        t002.append({'source': 'fdc_pinjaman', 'dedup_field': 'id_penyelenggara', 'window': w})
    # fdc_pinjaman.tipe_pinjaman: 4 windows
    for w in [30, 60, 90, 180]:
        t002.append({'source': 'fdc_pinjaman', 'dedup_field': 'tipe_pinjaman', 'window': w})
    # fdc_pinjaman.status_pinjaman: 4 windows
    for w in [30, 60, 90, 180]:
        t002.append({'source': 'fdc_pinjaman', 'dedup_field': 'status_pinjaman', 'window': w})
    combos['T002'] = t002  # 6 + 4 + 4 + 4 = 18

    # ---- T002 extensions: new windows + new dedup fields ----
    for w in [7, 15, 180]:
        t002.append({'source': 'fdc_inquiry', 'dedup_field': 'hit_by', 'window': w})
    for field in ['kualitas_pinjaman', 'pendanaan_syariah']:
        for w in [30, 60, 90, 180]:
            t002.append({'source': 'fdc_pinjaman', 'dedup_field': field, 'window': w})

    # ========== T003: decayed_sum ==========
    t003 = []
    # fdc_pinjaman nilai_pendanaan: 4 decay profiles x 4 windows
    for decay_func, decay_rate, label in [
        ('exponential', 0.05, 'e005'),
        ('exponential', 0.02, 'e002'),
        ('exponential', 0.1, 'e010'),
        ('linear', 0.5, 'lin05'),
    ]:
        for w in [30, 60, 90, 180]:
            t003.append({
                'source': 'fdc_pinjaman', 'window': w,
                'decay_func': decay_func, 'decay_rate': decay_rate,
                'value_field': 'nilai_pendanaan', 'vf_label': 'amt'
            })
    combos['T003'] = t003  # 4 x 4 = 16

    # ---- T003 extensions: new value_fields ----
    for vf, vf_label in [('sisa_pinjaman_berjalan', 'bal'), ('pendapatan', 'inc')]:
        for decay_func, decay_rate, label in [
            ('exponential', 0.05, 'e005'),
            ('exponential', 0.02, 'e002'),
            ('exponential', 0.1, 'e010'),
            ('linear', 0.5, 'lin05'),
        ]:
            for w in [30, 60, 90, 180]:
                t003.append({
                    'source': 'fdc_pinjaman', 'window': w,
                    'decay_func': decay_func, 'decay_rate': decay_rate,
                    'value_field': vf, 'vf_label': vf_label
                })

    # ========== T004: proportion ==========
    t004 = []
    # applist by category: 10 groups x 4 windows
    for cats, label in APPLIST_CATEGORY_GROUPS:
        for w in [7, 30, 60, 90]:
            t004.append({
                'source': 'applist', 'window': w,
                'allowed_categories': cats, 'use_by_category': True
            })
    # fdc_pinjaman target_cond: 8 conds x 4 windows
    for cond, label in FDC_PROP_TARGET_CONDS:
        for w in [30, 60, 90, 180]:
            t004.append({
                'source': 'fdc_pinjaman', 'window': w,
                'target_cond': cond, 'use_by_category': False
            })
    combos['T004'] = t004  # 40 + 32 = 72

    # ---- T004 extensions: new windows ----
    for cats, label in APPLIST_CATEGORY_GROUPS:
        for w in [3, 15]:
            t004.append({
                'source': 'applist', 'window': w,
                'allowed_categories': cats, 'use_by_category': True
            })
    for cond, label in FDC_PROP_TARGET_CONDS:
        for w in [7, 15]:
            t004.append({
                'source': 'fdc_pinjaman', 'window': w,
                'target_cond': cond, 'use_by_category': False
            })

    # ========== T005: concentration ==========
    t005 = []
    # fdc_pinjaman: 3 methods x 2 fields x 4 windows
    for method in ['gini', 'entropy', 'cv']:
        for cat_field in ['id_penyelenggara', 'tipe_pinjaman']:
            for w in [30, 60, 90, 180]:
                t005.append({
                    'source': 'fdc_pinjaman', 'window': w,
                    'method': method, 'category_field': cat_field
                })
    # applist by_category: 3 methods x 4 windows
    for method in ['entropy', 'gini']:
        for w in [30, 60, 90]:
            t005.append({
                'source': 'applist', 'window': w,
                'method': method, 'use_by_category': True
            })
    combos['T005'] = t005  # 24 + 8 = 32

    # ---- T005 extensions: new category_field kualitas_pinjaman ----
    for method in ['gini', 'entropy', 'cv']:
        for w in [30, 60, 90, 180]:
            t005.append({
                'source': 'fdc_pinjaman', 'window': w,
                'method': method, 'category_field': 'kualitas_pinjaman'
            })

    # ========== T006: overlap ==========
    t006 = []
    for w in [7, 30, 60, 90]:
        t006.append({
            'source_a': 'applist', 'field_a': 'packageX',
            'source_b': 'fdc_pinjaman', 'field_b': 'id_penyelenggara',
            'window': w
        })
    combos['T006'] = t006  # 4

    # ========== T007: period_compare ==========
    t007 = []
    for src, short, long in [
        ('fdc_inquiry', 3, 7),
        ('fdc_inquiry', 7, 30),
        ('fdc_inquiry', 15, 90),
        ('fdc_pinjaman', 7, 30),
        ('fdc_pinjaman', 30, 90),
        ('fdc_pinjaman', 30, 180),
        ('applist', 7, 30),
        ('applist', 15, 60),
    ]:
        t007.append({'source': src, 'short_window': short, 'long_window': long})
    combos['T007'] = t007  # 8

    # ---- T007 extensions ----
    for src, short, long in [
        ('fdc_inquiry', 30, 90),
        ('fdc_inquiry', 7, 90),
        ('fdc_pinjaman', 7, 90),
        ('fdc_pinjaman', 15, 90),
        ('applist', 30, 90),
    ]:
        t007.append({'source': src, 'short_window': short, 'long_window': long})

    # ========== T008: trend ==========
    t008 = []
    for src, windows in [
        ('fdc_inquiry', [7, 15, 30]),
        ('fdc_inquiry', [3, 7, 30]),
        ('fdc_pinjaman', [7, 30, 60]),
        ('fdc_pinjaman', [30, 60, 90]),
        ('fdc_pinjaman', [60, 90, 180]),
        ('applist', [7, 15, 30]),
        ('applist', [30, 60, 90]),
    ]:
        t008.append({'source': src, 'windows': windows})
    combos['T008'] = t008  # 7

    # ---- T008 extensions ----
    for src, windows in [
        ('fdc_pinjaman', [3, 7, 30]),
        ('fdc_pinjaman', [7, 30, 90]),
        ('applist', [3, 7, 30]),
        ('fdc_inquiry', [3, 7, 30]),
        ('fdc_inquiry', [7, 30, 90]),
    ]:
        t008.append({'source': src, 'windows': windows})

    # ========== T009: spike ==========
    t009 = []
    # fdc_inquiry 不适用（预聚合，总是返回0），跳过
    for src in ['applist', 'fdc_pinjaman']:
        for w in [15, 30, 60]:
            for thresh in [2.0, 3.0]:
                t009.append({
                    'source': src, 'window': w, 'threshold': thresh
                })
    combos['T009'] = t009  # 2 x 3 x 2 = 12

    # ---- T009 extensions: lower thresholds ----
    for src in ['applist', 'fdc_pinjaman']:
        for w in [7, 15, 30, 60]:
            for thresh in [1.5, 2.5]:
                t009.append({
                    'source': src, 'window': w, 'threshold': thresh
                })

    # ========== T010: percentile ==========
    t010 = [
        {'target_metric': 'salary'},
        {'target_metric': 'loan_amount'},
        {'target_metric': 'inquiry_count'},
        {'target_metric': 'applist_count'},
    ]
    combos['T010'] = t010  # 4

    # ========== T011: deviation ==========
    t011 = [
        {'target_metric': 'salary'},
        {'target_metric': 'loan_amount'},
        {'target_metric': 'inquiry_count'},
        {'target_metric': 'applist_count'},
    ]
    combos['T011'] = t011  # 4

    # ========== T012: anomaly ==========
    t012 = [
        {'target_metric': 'app_install_pattern', 'method': 'mahalanobis'},
        {'target_metric': 'loan_pattern', 'method': 'mahalanobis'},
    ]
    combos['T012'] = t012  # 2

    # ========== T013: declared_vs_actual ==========
    t013 = [
        {'declared_field': 'base.salary', 'actual_field': 'fdc_pinjaman.nilai_pendanaan', 'method': 'ratio'},
        {'declared_field': 'base.salary', 'actual_field': 'fdc_pinjaman.nilai_pendanaan', 'method': 'gap'},
        {'declared_field': 'base.salary', 'actual_field': 'fdc_pinjaman.nilai_pendanaan', 'method': 'abs_diff'},
    ]
    combos['T013'] = t013  # 3

    # ---- T013 extensions: salary vs pendapatan ----
    for method in ['ratio', 'gap', 'abs_diff']:
        t013.append({
            'declared_field': 'base.salary', 'actual_field': 'fdc_pinjaman.pendapatan', 'method': method
        })

    # ========== T014: cross_source_discrepancy ==========
    # 只保留语义可对比的字段对
    t014 = [
        {
            'field_pairs_config': [
                {'src': 'base', 'field': 'salary'},
                {'src': 'fdc_pinjaman', 'field': 'nilai_pendanaan'}
            ]
        },
    ]
    combos['T014'] = t014  # 1

    # ========== T015: identity_cluster ==========
    t015 = [
        {'identity_field': 'device_id', 'shared_field': 'packageX', 'min_threshold': 3},
        {'identity_field': 'device_id', 'shared_field': 'id_penyelenggara', 'min_threshold': 2},
    ]
    combos['T015'] = t015  # 2

    # ========== T016: derived/combination features ==========
    t016 = []

    # --- 1. ratio_density: count / window_days (event rate) ---
    for src, windows, sname in [
        ('applist', [7, 15, 30, 60, 90, 180], 'app'),
        ('fdc_pinjaman', [7, 15, 30, 60, 90, 180], 'fdcpin'),
        ('fdc_inquiry', [3, 7, 15, 30, 90, 180], 'fdciq'),
    ]:
        for w in windows:
            t016.append({
                'derived_type': 'ratio_density',
                'source': src,
                'window': w,
                'ref_feature_name': f'cnt_{sname}_{w}d',
                'label': f'{sname}_{w}d',
            })

    # --- 2. ratio_cross: feature_a / feature_b ---
    CROSS_RATIOS = [
        ('gambling_banking_30d', 'prop_app_gambling_30d', 'prop_app_banking_30d'),
        ('gambling_banking_90d', 'prop_app_gambling_90d', 'prop_app_banking_90d'),
        ('highrisk_banking_30d', 'prop_app_gambling_cash_loan_fintech_lending_30d', 'prop_app_banking_30d'),
        ('highrisk_banking_90d', 'prop_app_gambling_cash_loan_fintech_lending_90d', 'prop_app_banking_90d'),
        ('activeloan_30d', 'cnt_fdcpin_status_pinjaman_o_30d', 'cnt_fdcpin_30d'),
        ('writeoff_30d', 'cnt_fdcpin_status_pinjaman_w_30d', 'cnt_fdcpin_30d'),
        ('avg_loans_per_lender_30d', 'cnt_fdcpin_30d', 'uniq_fdcpin_lender_30d'),
        ('avg_loans_per_lender_90d', 'cnt_fdcpin_90d', 'uniq_fdcpin_lender_90d'),
        ('avg_amt_30d', 'decay_fdcpin_amt_30d_r005', 'cnt_fdcpin_30d'),
        ('avg_amt_180d', 'decay_fdcpin_amt_180d_r005', 'cnt_fdcpin_180d'),
        ('spending_conc_30v180', 'decay_fdcpin_amt_30d_r005', 'decay_fdcpin_amt_180d_r005'),
        ('deterioration_30d', 'prop_fdcpin_kualitas_pinjaman_3_30d', 'prop_fdcpin_kualitas_pinjaman_1_30d'),
        ('kualitas5_ratio_30d', 'prop_fdcpin_kualitas_pinjaman_5_30d', 'prop_fdcpin_kualitas_pinjaman_1_30d'),
    ]
    for label, feat_a, feat_b in CROSS_RATIOS:
        t016.append({
            'derived_type': 'ratio_cross',
            'label': label,
            'ref_feature_a': feat_a,
            'ref_feature_b': feat_b,
        })

    # --- 3. weighted_combo: feature_a * feature_b ---
    WEIGHTED_COMBOS = [
        ('riskexp_30d', 'prop_app_gambling_30d', 'cnt_fdcpin_status_pinjaman_o_30d'),
        ('riskexp_90d', 'prop_app_gambling_90d', 'cnt_fdcpin_status_pinjaman_o_90d'),
        ('highrisk_loan_30d', 'prop_app_gambling_cash_loan_fintech_lending_30d', 'cnt_fdcpin_30d'),
        ('highrisk_loan_90d', 'prop_app_gambling_cash_loan_fintech_lending_90d', 'cnt_fdcpin_90d'),
    ]
    for label, feat_a, feat_b in WEIGHTED_COMBOS:
        t016.append({
            'derived_type': 'weighted_combo',
            'label': label,
            'ref_feature_a': feat_a,
            'ref_feature_b': feat_b,
        })

    # --- 4. extended_velocity: (short/short_w) / (long/long_w) - 1 ---
    EXTENDED_VELOCITIES = [
        ('applist', 7, 90),
        ('fdc_pinjaman', 7, 30),
        ('fdc_pinjaman', 15, 90),
        ('fdc_pinjaman', 7, 180),
        ('fdc_inquiry', 3, 30),
        ('fdc_inquiry', 7, 90),
        ('fdc_inquiry', 3, 90),
        ('fdc_inquiry', 15, 180),
        ('uniq_lender', 30, 90),
    ]
    for src, short, long in EXTENDED_VELOCITIES:
        if src == 'uniq_lender':
            feat_short = f'uniq_fdcpin_lender_{short}d'
            feat_long = f'uniq_fdcpin_lender_{long}d'
        else:
            sname = {'fdc_inquiry': 'fdciq', 'fdc_pinjaman': 'fdcpin', 'applist': 'app'}[src]
            feat_short = f'cnt_{sname}_{short}d'
            feat_long = f'cnt_{sname}_{long}d'
        t016.append({
            'derived_type': 'extended_velocity',
            'source': src,
            'short_window': short,
            'long_window': long,
            'ref_feature_short': feat_short,
            'ref_feature_long': feat_long,
        })

    # --- 5. squared ---
    SQUARED_FEATURES = [
        'cnt_fdcpin_30d', 'cnt_fdcpin_90d', 'cnt_fdcpin_180d',
        'cnt_app_30d', 'cnt_app_90d',
        'cnt_fdciq_30d', 'cnt_fdciq_90d',
        'uniq_fdcpin_lender_30d', 'uniq_fdcpin_lender_90d',
    ]
    for feat_name in SQUARED_FEATURES:
        t016.append({
            'derived_type': 'squared',
            'ref_feature_name': feat_name,
            'label': feat_name,
        })

    # --- 6. log_transform ---
    LOG_FEATURES = [
        'cnt_fdcpin_30d', 'cnt_fdcpin_90d', 'cnt_fdcpin_180d',
        'cnt_app_30d', 'cnt_app_90d',
        'cnt_fdciq_30d', 'cnt_fdciq_90d',
        'uniq_fdcpin_lender_30d', 'uniq_fdcpin_lender_90d',
        'decay_fdcpin_amt_30d_r005', 'decay_fdcpin_amt_180d_r005',
    ]
    for feat_name in LOG_FEATURES:
        t016.append({
            'derived_type': 'log_transform',
            'ref_feature_name': feat_name,
            'label': feat_name,
        })

    combos['T016'] = t016  # ~66 derived features

    # ========== T016 extensions: more derived features ==========

    # --- More ratio_cross ---
    for label, feat_a, feat_b in [
        ('gambling_ewallet_30d', 'prop_app_gambling_30d', 'prop_app_ewallet_30d'),
        ('gambling_ewallet_90d', 'prop_app_gambling_90d', 'prop_app_ewallet_90d'),
        ('highrisk_consume_30d', 'prop_app_gambling_cash_loan_fintech_lending_30d', 'prop_app_shopping_food_delivery_30d'),
        ('highrisk_consume_90d', 'prop_app_gambling_cash_loan_fintech_lending_90d', 'prop_app_shopping_food_delivery_90d'),
        ('avg_loan_per_lender_30d', 'cnt_fdcpin_30d', 'uniq_fdcpin_lender_30d'),
        ('avg_loan_per_lender_90d', 'cnt_fdcpin_90d', 'uniq_fdcpin_lender_90d'),
        ('perc_active_30d', 'cnt_fdcpin_status_pinjaman_o_30d', 'cnt_fdcpin_30d'),
        ('perc_active_90d', 'cnt_fdcpin_status_pinjaman_o_90d', 'cnt_fdcpin_90d'),
        ('new_ratio_30d', 'cnt_fdcpin_360d', 'cnt_fdcpin_30d'),
        ('new_ratio_90d', 'cnt_fdcpin_360d', 'cnt_fdcpin_90d'),
    ]:
        t016.append({
            'derived_type': 'ratio_cross',
            'label': label,
            'ref_feature_a': feat_a,
            'ref_feature_b': feat_b,
        })

    # --- More weighted_combo ---
    for label, feat_a, feat_b in [
        ('highrisk_dpd30_30d', 'prop_app_gambling_cash_loan_fintech_lending_30d', 'cnt_fdcpin_30d'),
        ('highrisk_dpd30_90d', 'prop_app_gambling_cash_loan_fintech_lending_90d', 'cnt_fdcpin_90d'),
        ('gambling_dpd30_30d', 'prop_app_gambling_30d', 'cnt_fdcpin_30d'),
        ('gambling_dpd30_90d', 'prop_app_gambling_90d', 'cnt_fdcpin_90d'),
        ('loanvol_lender_30d', 'cnt_fdcpin_30d', 'uniq_fdcpin_lender_30d'),
        ('loanvol_lender_90d', 'cnt_fdcpin_90d', 'uniq_fdcpin_lender_90d'),
        ('risk_balance_30d', 'prop_app_gambling_cash_loan_fintech_lending_30d', 'decay_fdcpin_bal_30d_r005'),
        ('risk_balance_90d', 'prop_app_gambling_cash_loan_fintech_lending_90d', 'decay_fdcpin_bal_90d_r005'),
    ]:
        t016.append({
            'derived_type': 'weighted_combo',
            'label': label,
            'ref_feature_a': feat_a,
            'ref_feature_b': feat_b,
        })

    # --- More extended_velocity ---
    for src, short, long, feat_short, feat_long in [
        ('applist', 7, 90, 'cnt_app_7d', 'cnt_app_90d'),
        ('fdc_pinjaman', 7, 90, 'cnt_fdcpin_7d', 'cnt_fdcpin_90d'),
        ('fdc_pinjaman', 15, 90, 'cnt_fdcpin_15d', 'cnt_fdcpin_90d'),
        ('fdc_inquiry', 3, 30, 'cnt_fdciq_3d', 'cnt_fdciq_30d'),
        ('fdc_inquiry', 7, 30, 'cnt_fdciq_7d', 'cnt_fdciq_30d'),
    ]:
        t016.append({
            'derived_type': 'extended_velocity',
            'source': src,
            'short_window': short,
            'long_window': long,
            'ref_feature_short': feat_short,
            'ref_feature_long': feat_long,
        })

    # --- More squared ---
    for feat_name in [
        'cnt_fdcpin_360d', 'cnt_app_360d', 'cnt_fdciq_360d',
        'uniq_fdcpin_lender_180d',
        'prop_app_gambling_cash_loan_fintech_lending_30d',
        'prop_app_gambling_cash_loan_fintech_lending_90d',
        'perc_fdciq_3v7d', 'perc_app_7v30d',
        'trend_fdcpin_30_60_90d', 'trend_fdciq_7_15_30d',
        'decay_fdcpin_bal_30d_r005', 'decay_fdcpin_inc_90d_r005',
    ]:
        t016.append({
            'derived_type': 'squared',
            'ref_feature_name': feat_name,
            'label': feat_name,
        })

    # --- More log_transform ---
    for feat_name in [
        'cnt_fdcpin_360d', 'cnt_app_360d',
        'uniq_fdcpin_lender_180d',
        'prop_app_gambling_cash_loan_fintech_lending_30d',
        'decay_fdcpin_bal_30d_r005', 'decay_fdcpin_bal_90d_r005',
        'decay_fdcpin_inc_30d_r005', 'decay_fdcpin_inc_90d_r005',
        'spike_app_30d_2x0', 'spike_fdcpin_30d_2x0',
    ]:
        t016.append({
            'derived_type': 'log_transform',
            'ref_feature_name': feat_name,
            'label': feat_name,
        })

    # --- New: difference features ---
    for label, feat_a, feat_b in [
        ('amt_vs_bal_60d', 'decay_fdcpin_amt_60d_r005', 'decay_fdcpin_bal_60d_r005'),
        ('amt_vs_bal_180d', 'decay_fdcpin_amt_180d_r005', 'decay_fdcpin_bal_180d_r005'),
        ('bal_vs_inc_60d', 'decay_fdcpin_bal_60d_r005', 'decay_fdcpin_inc_60d_r005'),
        ('bal_vs_inc_90d', 'decay_fdcpin_bal_90d_r005', 'decay_fdcpin_inc_90d_r005'),
        ('spike_app_vs_pinjaman_30d', 'spike_app_30d_2x0', 'spike_fdcpin_30d_2x0'),
    ]:
        t016.append({
            'derived_type': 'difference',
            'label': label,
            'ref_feature_a': feat_a,
            'ref_feature_b': feat_b,
        })

    # --- New: is_high (binary flags) ---
    for feat_name in [
        'cnt_fdcpin_360d', 'cnt_app_360d',
        'uniq_fdcpin_lender_30d', 'uniq_fdcpin_lender_90d',
        'decay_fdcpin_amt_30d_r005', 'decay_fdcpin_amt_90d_r005',
        'decay_fdcpin_bal_30d_r005',
        'prop_app_gambling_cash_loan_fintech_lending_30d',
        'conc_fdcpin_penyelenggara_gini_90d',
        'perc_fdciq_3v7d',
    ]:
        t016.append({
            'derived_type': 'is_high',
            'ref_feature_name': feat_name,
            'label': feat_name,
        })

    return combos


def _validate_t016_references(t016_combos: list, all_combos: dict):
    """Cross-check all T016 ref_feature references against actual primary feature names.

    Raises ValueError with all missing references to prevent silent NameErrors
    in generated code.
    """
    # Build set of all primary feature names (T001-T015)
    primary_names = set()
    for tid, combos in all_combos.items():
        if tid == 'T016':
            continue
        for params in combos:
            primary_names.add(_generate_feature_name(tid, params))

    # Collect all ref_feature names referenced by T016
    referenced = set()
    for entry in t016_combos:
        for key in ('ref_feature_name', 'ref_feature_a', 'ref_feature_b',
                     'ref_feature_short', 'ref_feature_long'):
            val = entry.get(key)
            if val:
                referenced.add(val)

    missing = sorted(referenced - primary_names)
    if missing:
        msg = (
            f"T016 validation FAILED: {len(missing)} referenced feature(s) "
            f"do not exist as primary features:\n"
        )
        for name in missing:
            msg += f"  - {name}\n"
        raise ValueError(msg)

    if referenced:
        print(f"[T016 validation] OK — all {len(referenced)} referenced features exist "
              f"in primary set ({len(primary_names)} total)")
    else:
        print("[T016 validation] No T016 features to validate")


PARAM_COMBOS = _build_param_combos()


# ============================================================
# 确定性命名函数
# ============================================================

def _short_source(src: str) -> str:
    m = {
        'fdc_inquiry': 'fdciq',
        'fdc_pinjaman': 'fdcpin',
        'applist': 'app',
    }
    return m.get(src, src)


def _generate_feature_name(tid: str, params: Dict) -> str:
    """确定性生成特征名（无LLM）"""
    if tid == 'T001':
        src = params.get('source', '')
        sname = _short_source(src)
        w = params.get('window', 30)
        cond = params.get('cond', {})
        if cond:
            k = list(cond.keys())[0]
            v = str(cond[k]).lower().replace(' ', '')
            return f"cnt_{sname}_{k}_{v}_{w}d"
        return f"cnt_{sname}_{w}d"

    elif tid == 'T002':
        src = params.get('source', '')
        dedup = params.get('dedup_field', '')
        w = params.get('window', 30)
        dedup_map = {
            'hit_by': 'hitby',
            'id_penyelenggara': 'lender',
            'tipe_pinjaman': 'loan_type',
            'status_pinjaman': 'loan_status',
        }
        dshort = dedup_map.get(dedup, dedup.replace('id_', '').replace('tipe_', '').replace('status_', ''))
        return f"uniq_{_short_source(src)}_{dshort}_{w}d"

    elif tid == 'T003':
        src = 'fdcpin'
        w = params.get('window', 90)
        rate_key = str(params.get('decay_rate', '')).replace('.', '')
        vf_label = params.get('vf_label', 'amt')
        return f"decay_{src}_{vf_label}_{w}d_r{rate_key}"

    elif tid == 'T004':
        src = params.get('source', '')
        w = params.get('window', 30)
        use_cat = params.get('use_by_category', False)
        if use_cat:
            cats = params.get('allowed_categories', ['unknown'])
            label = '_'.join(cats)
            return f"prop_{_short_source(src)}_{label}_{w}d"
        else:
            cond = params.get('target_cond', {})
            k = list(cond.keys())[0]
            v = str(cond[k]).lower().replace(' ', '')
            return f"prop_{_short_source(src)}_{k}_{v}_{w}d"

    elif tid == 'T005':
        method = params.get('method', 'gini')
        src = params.get('source', '')
        w = params.get('window', 90)
        if params.get('use_by_category'):
            return f"conc_{_short_source(src)}_cat_{method}_{w}d"
        cat_f = params.get('category_field', '').replace('id_', '').replace('tipe_', '')
        return f"conc_{_short_source(src)}_{cat_f}_{method}_{w}d"

    elif tid == 'T006':
        w = params.get('window', 30)
        return f"ovlap_app_fdc_{w}d"

    elif tid == 'T007':
        src = params.get('source', '')
        s = params.get('short_window', 7)
        l = params.get('long_window', 30)
        return f"perc_{_short_source(src)}_{s}v{l}d"

    elif tid == 'T008':
        src = params.get('source', '')
        wins = params.get('windows', [7, 15, 30])
        wstr = '_'.join(str(w) for w in wins)
        return f"trend_{_short_source(src)}_{wstr}d"

    elif tid == 'T009':
        src = params.get('source', '')
        w = params.get('window', 30)
        th = str(params.get('threshold', 3.0)).replace('.', 'x')
        return f"spike_{_short_source(src)}_{w}d_{th}"

    elif tid == 'T010':
        metric = params.get('target_metric', 'salary')
        return f"pctl_{metric}_pop"

    elif tid == 'T011':
        metric = params.get('target_metric', 'salary')
        return f"dev_{metric}_peer"

    elif tid == 'T012':
        metric = params.get('target_metric', 'app_install_pattern')
        mshort = metric.replace('app_install_pattern', 'app').replace('loan_pattern', 'loan')
        return f"anom_{mshort}"

    elif tid == 'T013':
        method = params.get('method', 'ratio')
        return f"da_salary_loan_{method}"

    elif tid == 'T014':
        return "disc_salary_loan"

    elif tid == 'T015':
        shared = params.get('shared_field', 'packageX').replace('id_', '').replace('packageX', 'pkg')
        return f"cluster_device_{shared}"

    elif tid == 'T016':
        dtype = params.get('derived_type', '')
        if dtype == 'ratio_density':
            src = params.get('source', '')
            w = params.get('window', 30)
            return f"d_dens_{_short_source(src)}_{w}d"
        elif dtype == 'ratio_cross':
            label = params.get('label', 'cross')
            return f"d_ratio_{label}"
        elif dtype == 'weighted_combo':
            label = params.get('label', 'combo')
            return f"d_wcomb_{label}"
        elif dtype == 'extended_velocity':
            src = params.get('source', '')
            s = params.get('short_window', 3)
            l = params.get('long_window', 7)
            if src == 'uniq_lender':
                return f"d_vel_lender_{s}v{l}d"
            return f"d_vel_{_short_source(src)}_{s}v{l}d"
        elif dtype == 'squared':
            ref_name = params.get('ref_feature_name', 'feat')
            return f"d_sq_{ref_name}"
        elif dtype == 'log_transform':
            ref_name = params.get('ref_feature_name', 'feat')
            return f"d_log_{ref_name}"
        elif dtype == 'difference':
            label = params.get('label', 'diff')
            return f"d_diff_{label}"
        elif dtype == 'is_high':
            ref_name = params.get('ref_feature_name', 'feat')
            return f"d_high_{ref_name}"
        return f"d_derived_{params.get('label', 'unknown')}"

    return f"feat_{tid}".lower()


# ============================================================
# 获取对应计算函数名
# ============================================================

def _get_func_name(tid: str, params: Dict) -> str:
    """根据模板ID和参数确定调用的计算函数"""
    func_map = {
        'T001': 'calc_count',
        'T002': 'calc_distinct_count',
        'T003': 'calc_decayed_sum',
        'T005': 'calc_concentration',
        'T006': 'calc_overlap',
        'T007': 'calc_period_compare',
        'T008': 'calc_trend',
        'T009': 'calc_spike',
        'T010': 'calc_percentile',
        'T011': 'calc_deviation',
        'T012': 'calc_anomaly',
        'T013': 'calc_declared_vs_actual',
        'T014': 'calc_cross_discrepancy',
        'T015': 'calc_identity_cluster',
    }
    if tid == 'T004':
        if params.get('use_by_category'):
            return 'calc_proportion_by_category'
        return 'calc_proportion'

    if tid == 'T016':
        return None  # T016 is pure arithmetic, no external function needed

    return func_map.get(tid, 'calc_count')


# ============================================================
# 参数 → kwargs 转换
# ============================================================

def _params_to_kwargs(tid: str, params: Dict) -> Dict:
    """将设计参数转换为函数关键字参数"""
    if tid == 'T001':
        return {
            'field_set': params['source'],
            'window_days': params['window'],
            'cond': params.get('cond'),
        }
    elif tid == 'T002':
        return {
            'field_set': params['source'],
            'window_days': params['window'],
            'dedup_field': params['dedup_field'],
        }
    elif tid == 'T003':
        return {
            'field_set': params['source'],
            'window_days': params['window'],
            'decay_func': params['decay_func'],
            'decay_rate': params['decay_rate'],
            'value_field': params.get('value_field'),
        }
    elif tid == 'T004':
        if params.get('use_by_category'):
            return {
                'window_days': params['window'],
                'allowed_categories': set(params['allowed_categories']),
                'category_cache': 'self.app_category_cache',
            }
        return {
            'source': params['source'],
            'window_days': params['window'],
            'target_cond': params['target_cond'],
        }
    elif tid == 'T005':
        if params.get('use_by_category'):
            return {
                'window_days': params['window'],
                'method': params['method'],
                'category_cache': 'self.app_category_cache',
            }
        return {
            'field_set': params['source'],
            'window_days': params['window'],
            'method': params['method'],
            'category_field': params['category_field'],
        }
    elif tid == 'T006':
        return {
            'source_a': params['source_a'],
            'field_a': params['field_a'],
            'source_b': params['source_b'],
            'field_b': params['field_b'],
            'window_days': params['window'],
        }
    elif tid == 'T007':
        return {
            'field_set': params['source'],
            'short_window': params['short_window'],
            'long_window': params['long_window'],
        }
    elif tid == 'T008':
        return {
            'field_set': params['source'],
            'windows': params['windows'],
        }
    elif tid == 'T009':
        return {
            'field_set': params['source'],
            'window_days': params['window'],
            'threshold': params['threshold'],
        }
    elif tid == 'T010':
        return {'target_metric': params['target_metric']}
    elif tid == 'T011':
        return {'target_metric': params['target_metric']}
    elif tid == 'T012':
        return {'target_metric': params['target_metric'], 'method': params.get('method', 'mahalanobis')}
    elif tid == 'T013':
        return {
            'declared_field': params['declared_field'],
            'actual_field': params['actual_field'],
            'method': params['method'],
        }
    elif tid == 'T014':
        return {'field_pairs': params['field_pairs_config']}
    elif tid == 'T015':
        return {
            'identity_field': params['identity_field'],
            'shared_field': params['shared_field'],
        }
    return {}


# ============================================================
# 参考分布预计算
# ============================================================

def precompute_references(train_data: List[Dict]) -> Dict:
    """从训练数据预计算T010-T012所需的参考分布

    Args:
        train_data: 训练样本列表

    Returns:
        包含参考分布的字典
    """
    salaries = []
    loan_amounts = []
    inquiry_counts = []
    applist_counts = []
    app_count_features = []
    loan_vecs = []

    for sample in train_data:
        try:
            base = sample.get('params', {}).get('base', {})
            salary = base.get('salary', 0)
            if salary and salary > 0:
                salaries.append(float(salary))

            fdc = sample.get('params', {}).get('FDC', {})
            pinjaman = fdc.get('pinjaman', [])
            amounts = [float(p.get('nilai_pendanaan', 0)) for p in pinjaman if p.get('nilai_pendanaan')]
            if amounts:
                loan_amounts.append(max(amounts))
                # 贷款特征向量: [贷款笔数, 最大金额, 平均金额, 活跃机构数]
            lenders = set(p.get('id_penyelenggara', '') for p in pinjaman if p.get('id_penyelenggara'))
            loan_vec = [
                len(pinjaman),
                max(amounts) if amounts else 0,
                sum(amounts) / len(amounts) if amounts else 0,
                len(lenders),
            ]
            loan_vecs.append(loan_vec)

            inquiry = fdc.get('history_inquiry', {})
            stat = inquiry.get('statistic', {})
            inq = stat.get('30_hari', 0)
            inquiry_counts.append(float(inq))

            applist = sample.get('params', {}).get('appList', [])
            applist_counts.append(len(applist))
            # APP特征向量: [app总数, 系统app数, 非系统app数]
            sys_count = sum(1 for a in applist if a.get('sysApp') == 1)
            app_count_features.append([len(applist), sys_count, len(applist) - sys_count])
        except Exception:
            continue

    refs = {
        'salary_distribution': salaries,
        'salary_mean': float(np.mean(salaries)) if salaries else 0.0,
        'salary_std': float(np.std(salaries)) if salaries else 0.0,
        'loan_amount_distribution': loan_amounts,
        'loan_amount_mean': float(np.mean(loan_amounts)) if loan_amounts else 0.0,
        'loan_amount_std': float(np.std(loan_amounts)) if loan_amounts else 0.0,
        'inquiry_count_distribution': inquiry_counts,
        'inquiry_count_mean': float(np.mean(inquiry_counts)) if inquiry_counts else 0.0,
        'inquiry_count_std': float(np.std(inquiry_counts)) if inquiry_counts else 0.0,
        'applist_count_distribution': applist_counts,
        'applist_count_mean': float(np.mean(applist_counts)) if applist_counts else 0.0,
        'applist_count_std': float(np.std(applist_counts)) if applist_counts else 0.0,
        'loan_feature_vectors': loan_vecs,
        'app_feature_vectors': app_count_features,
    }
    return refs


# ============================================================
# 代码生成
# ============================================================

def _get_gen_func_name(tid: str, params: Dict) -> str:
    """获取需要导入的计算函数名"""
    tid_func_map = {
        'T001': 'calc_count', 'T002': 'calc_distinct_count',
        'T003': 'calc_decayed_sum', 'T006': 'calc_overlap',
        'T007': 'calc_period_compare', 'T008': 'calc_trend',
        'T009': 'calc_spike', 'T010': 'calc_percentile',
        'T011': 'calc_deviation', 'T012': 'calc_anomaly',
        'T013': 'calc_declared_vs_actual', 'T014': 'calc_cross_discrepancy',
        'T015': 'calc_identity_cluster',
    }
    if tid == 'T004':
        return 'calc_proportion_by_category' if params.get('use_by_category') else 'calc_proportion'
    if tid == 'T005':
        return 'calc_concentration_by_category' if params.get('use_by_category') else 'calc_concentration'
    if tid == 'T016':
        return None  # T016 is pure arithmetic, no import needed
    return tid_func_map.get(tid, 'calc_count')


def _collect_func_names() -> List[str]:
    """收集所有需要的计算函数名"""
    names = set()
    for tid, combos_list in PARAM_COMBOS.items():
        if tid == 'T016':
            continue  # T016 is pure arithmetic, no channel1 imports needed
        for params in combos_list:
            fn = _get_gen_func_name(tid, params)
            if fn:
                names.add(fn)
    return sorted(names)


def _helper_functions_code() -> str:
    """生成T010-T012的数据提取辅助函数"""
    return """
    def _get_apply_time(self, data):
        return data.get('applyTime') or data.get('params', {}).get('base', {}).get('applyTime', 0)

    def _get_salary_from_data(self, data):
        try:
            return float(data.get('params', {}).get('base', {}).get('salary', 0))
        except (ValueError, TypeError):
            return 0.0

    def _get_loan_amount_from_data(self, data):
        try:
            pinjaman = data.get('params', {}).get('FDC', {}).get('pinjaman', [])
            amounts = [float(p.get('nilai_pendanaan', 0)) for p in pinjaman if p.get('nilai_pendanaan')]
            return max(amounts) if amounts else 0.0
        except:
            return 0.0

    def _get_inquiry_count_from_data(self, data):
        try:
            stat = data.get('params', {}).get('FDC', {}).get('history_inquiry', {}).get('statistic', {})
            return float(stat.get('30_hari', 0))
        except:
            return 0.0

    def _get_applist_count_from_data(self, data):
        try:
            return float(len(data.get('params', {}).get('appList', [])))
        except:
            return 0.0

    def _get_app_install_pattern_vector(self, data):
        try:
            applist = data.get('params', {}).get('appList', [])
            total = len(applist)
            sys_count = sum(1 for a in applist if a.get('sysApp') == 1)
            return [float(total), float(sys_count), float(total - sys_count)]
        except:
            return [0.0, 0.0, 0.0]

    def _get_loan_pattern_vector(self, data):
        try:
            pinjaman = data.get('params', {}).get('FDC', {}).get('pinjaman', [])
            amounts = [float(p.get('nilai_pendanaan', 0)) for p in pinjaman if p.get('nilai_pendanaan')]
            lenders = set(p.get('id_penyelenggara', '') for p in pinjaman if p.get('id_penyelenggara'))
            total_loans = len(pinjaman)
            max_amt = max(amounts) if amounts else 0
            avg_amt = sum(amounts) / len(amounts) if amounts else 0
            return [float(total_loans), float(max_amt), float(avg_amt), float(len(lenders))]
        except:
            return [0.0, 0.0, 0.0, 0.0]
"""

def _build_kwargs_code(tid: str, params: Dict) -> str:
    """构建函数调用的kwargs字符串"""
    parts = []
    if tid == 'T001':
        parts.append(f"field_set={repr(params['source'])}")
        parts.append(f"window_days={params['window']}")
        if params.get('cond'):
            parts.append(f"cond={repr(params['cond'])}")
    elif tid == 'T002':
        parts.append(f"field_set={repr(params['source'])}")
        parts.append(f"window_days={params['window']}")
        parts.append(f"dedup_field={repr(params['dedup_field'])}")
    elif tid == 'T003':
        parts.append(f"field_set={repr(params['source'])}")
        parts.append(f"window_days={params['window']}")
        parts.append(f"decay_func={repr(params['decay_func'])}")
        parts.append(f"decay_rate={params['decay_rate']}")
        if params.get('value_field'):
            parts.append(f"value_field={repr(params['value_field'])}")
    elif tid == 'T004':
        parts.append(f"window_days={params['window']}")
        if params.get('use_by_category'):
            parts.append(f"allowed_categories={repr(set(params['allowed_categories']))}")
            parts.append("category_cache=self.app_category_cache")
        else:
            parts.append(f"source={repr(params['source'])}")
            parts.append(f"target_cond={repr(params['target_cond'])}")
    elif tid == 'T005':
        parts.append(f"window_days={params['window']}")
        parts.append(f"method={repr(params['method'])}")
        if params.get('use_by_category'):
            parts.append("category_cache=self.app_category_cache")
        else:
            parts.append(f"field_set={repr(params['source'])}")
            parts.append(f"category_field={repr(params['category_field'])}")
    elif tid == 'T006':
        parts.append(f"source_a={repr(params['source_a'])}")
        parts.append(f"field_a={repr(params['field_a'])}")
        parts.append(f"source_b={repr(params['source_b'])}")
        parts.append(f"field_b={repr(params['field_b'])}")
        parts.append(f"window_days={params['window']}")
    elif tid == 'T007':
        parts.append(f"field_set={repr(params['source'])}")
        parts.append(f"short_window={params['short_window']}")
        parts.append(f"long_window={params['long_window']}")
    elif tid == 'T008':
        parts.append(f"field_set={repr(params['source'])}")
        parts.append(f"windows={repr(params['windows'])}")
    elif tid == 'T009':
        parts.append(f"field_set={repr(params['source'])}")
        parts.append(f"window_days={params['window']}")
        parts.append(f"threshold={params['threshold']}")
    elif tid == 'T010':
        metric = params['target_metric']
        parts.append(f"value=self._get_{metric}_from_data(data)")
        parts.append(f"reference_distribution=self.ref_distributions.get('{metric}_distribution', [])")
    elif tid == 'T011':
        metric = params['target_metric']
        parts.append(f"value=self._get_{metric}_from_data(data)")
        parts.append(f"ref_mean=self.ref_distributions.get('{metric}_mean', 0)")
        parts.append(f"ref_std=self.ref_distributions.get('{metric}_std', 1)")
    elif tid == 'T012':
        vec_map = {'app_install_pattern': 'app_feature_vectors', 'loan_pattern': 'loan_feature_vectors'}
        vec_key = vec_map.get(params['target_metric'], 'app_feature_vectors')
        parts.append(f"feature_vector=self._get_{params['target_metric']}_vector(data)")
        parts.append(f"reference_matrix=self.ref_distributions.get('{vec_key}', [])")
        parts.append(f"method={repr(params.get('method', 'mahalanobis'))}")
    elif tid == 'T013':
        parts.append(f"declared_field={repr(params['declared_field'])}")
        parts.append(f"actual_field={repr(params['actual_field'])}")
        parts.append(f"method={repr(params['method'])}")
    elif tid == 'T014':
        parts.append(f"field_pairs={repr(params['field_pairs_config'])}")
    elif tid == 'T015':
        parts.append(f"identity_field={repr(params['identity_field'])}")
        parts.append(f"shared_field={repr(params['shared_field'])}")
    return ', '.join(parts)


def _compose_T016(t016_params: Dict) -> str:
    """Generate a single line of code for a T016 derived feature"""
    dtype = t016_params['derived_type']
    fname = _generate_feature_name('T016', t016_params)

    if dtype == 'ratio_density':
        ref = t016_params['ref_feature_name']
        w = t016_params['window']
        return f"        {fname} = {ref} / {w}.0 if {ref} > 0 else 0.0"

    elif dtype == 'ratio_cross':
        a = t016_params['ref_feature_a']
        b = t016_params['ref_feature_b']
        return f"        {fname} = {a} / {b} if {b} != 0 else 0.0"

    elif dtype == 'weighted_combo':
        a = t016_params['ref_feature_a']
        b = t016_params['ref_feature_b']
        return f"        {fname} = {a} * {b}"

    elif dtype == 'extended_velocity':
        short_feat = t016_params['ref_feature_short']
        long_feat = t016_params['ref_feature_long']
        sw = t016_params['short_window']
        lw = t016_params['long_window']
        return (f"        {fname} = (({short_feat} / {sw}.0) / ({long_feat} / {lw}.0) - 1.0) "
                f"if {long_feat} > 0 else 0.0")

    elif dtype == 'squared':
        ref = t016_params['ref_feature_name']
        return f"        {fname} = {ref} ** 2"

    elif dtype == 'log_transform':
        ref = t016_params['ref_feature_name']
        return f"        {fname} = math.log({ref} + 1) if {ref} >= 0 else 0.0"

    elif dtype == 'difference':
        a = t016_params['ref_feature_a']
        b = t016_params['ref_feature_b']
        return f"        {fname} = {a} - {b}"

    elif dtype == 'is_high':
        ref = t016_params['ref_feature_name']
        return f"        {fname} = 1.0 if {ref} > 0 else 0.0"

    return f"        {fname} = 0.0  # unknown derived type: {dtype}"


def _compose_code(total_features: int) -> str:
    """组合生成完整的FeatureCalculator类代码"""
    func_names = _collect_func_names()

    lines = []
    lines.append('"""')
    lines.append('Feature Calculator - Mass Production Mode')
    lines.append('Auto-generated by feature_mass_producer.py')
    lines.append(f'Total features: {total_features}')
    lines.append('"""')
    lines.append('')
    lines.append('import math')
    lines.append('import os')
    lines.append('import sys')
    lines.append('from datetime import datetime')
    lines.append('from typing import Dict, List, Optional')
    lines.append('')
    lines.append('_ch1_dir = os.path.dirname(os.path.abspath(__file__))')
    lines.append('if _ch1_dir not in sys.path:')
    lines.append('    sys.path.insert(0, _ch1_dir)')
    lines.append('')
    lines.append('from channel1_calculators import (')
    for i, fn in enumerate(func_names):
        comma = ',' if i < len(func_names) - 1 else ''
        lines.append(f'    {fn}{comma}')
    lines.append(')')
    lines.append('')

    lines.append('')
    lines.append('class FeatureCalculator:')
    lines.append('    """Mass-produced feature calculator"""')
    lines.append('')
    lines.append('    def __init__(self, app_category_cache=None, ref_distributions=None):')
    lines.append('        self.app_category_cache = app_category_cache or {}')
    lines.append('        self.ref_distributions = ref_distributions or {}')
    lines.append('        self.gambling_packages = {pkg for pkg, info in self.app_category_cache.items()')
    lines.append('                                   if info.get("category") == "gambling"}')
    lines.append('        self.loan_packages = {pkg for pkg, info in self.app_category_cache.items()')
    lines.append('                               if info.get("category") in ("cash_loan", "fintech_lending")}')
    lines.append('')

    # 辅助函数
    helper_code = _helper_functions_code()
    for line in helper_code.split('\n'):
        if line.strip():
            lines.append(line)
    lines.append('')

    # calculate_all 方法
    lines.append('    def calculate_all(self, data, apply_time=None) -> dict:')
    lines.append('        if apply_time is None:')
    lines.append('            apply_time = self._get_apply_time(data)')
    lines.append('        if apply_time == 0:')
    lines.append('            return {}')
    lines.append('')
    lines.append('        apply_dt = datetime.fromtimestamp(apply_time / 1000)')
    lines.append('')

    # 特征计算（T001-T015 主特征）
    for tid in sorted(PARAM_COMBOS.keys()):
        if tid == 'T016':
            continue  # T016 derived features are computed in a separate block
        combos_list = PARAM_COMBOS[tid]
        for params in combos_list:
            fname = _generate_feature_name(tid, params)
            func_name = _get_gen_func_name(tid, params)
            kwargs_code = _build_kwargs_code(tid, params)

            lines.append(f'        # {fname}')
            if tid in ('T010', 'T011', 'T012'):
                call = f'{func_name}({kwargs_code})'
            elif tid in ('T013', 'T014', 'T015'):
                call = f'{func_name}(data, {kwargs_code})'
            else:
                call = f'{func_name}(data, {kwargs_code}, apply_time_dt=apply_dt)'
            lines.append(f'        {fname} = {call}')
            lines.append('')

    # ===== Derived Features (T016) =====
    # These combine primary features above to capture ratio/velocity/nonlinear signals
    if 'T016' in PARAM_COMBOS:
        lines.append('        # ===== Derived Features (T016) =====')
        for params in PARAM_COMBOS['T016']:
            fname = _generate_feature_name('T016', params)
            code_line = _compose_T016(params)
            lines.append(f'        # {fname}')
            lines.append(code_line)
            lines.append('')

    # return语句
    last_tid = sorted(PARAM_COMBOS.keys())[-1]
    lines.append('        return {')
    for tid in sorted(PARAM_COMBOS.keys()):
        combos_list = PARAM_COMBOS[tid]
        for i, params in enumerate(combos_list):
            fname = _generate_feature_name(tid, params)
            is_last = tid == last_tid and i == len(combos_list) - 1
            comma = '' if is_last else ','
            lines.append(f"            '{fname}': {fname}{comma}")
    lines.append('        }')

    return '\n'.join(lines)


def produce_all_features(ref_distributions: Dict = None) -> str:
    """生成完整的特征计算代码

    Args:
        ref_distributions: 预计算的参考分布

    Returns:
        完整的Python代码
    """
    total = sum(len(combos) for combos in PARAM_COMBOS.values())
    code = _compose_code(total)
    return code


def save_feature_calculator(code: str, output_path: str = None) -> str:
    """将生成的代码写入文件"""
    if output_path is None:
        output_path = 'outputs/feature_code/features_calculator_v2.py'
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(code)
    return output_path


def save_reference_distributions(refs: Dict, output_path: str = None) -> str:
    """保存参考分布到JSON"""
    if output_path is None:
        output_path = 'outputs/feature_code/reference_distributions.json'
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    clean = {}
    for k, v in refs.items():
        if isinstance(v, np.ndarray):
            clean[k] = v.tolist()
        elif isinstance(v, (np.floating,)):
            clean[k] = float(v)
        elif isinstance(v, (np.integer,)):
            clean[k] = int(v)
        elif isinstance(v, list):
            vals = []
            for item in v:
                if isinstance(item, np.ndarray):
                    vals.append(item.tolist())
                elif isinstance(item, (np.floating, np.integer)):
                    vals.append(float(item))
                else:
                    vals.append(item)
            clean[k] = vals
        else:
            clean[k] = v
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)
    return output_path


if __name__ == '__main__':
    # 测试：生成代码并验证
    import numpy as np
    code = produce_all_features()
    total_features = sum(len(combos) for combos in PARAM_COMBOS.values())
    primary_count = sum(len(combos) for tid, combos in PARAM_COMBOS.items() if tid != 'T016')
    derived_count = len(PARAM_COMBOS.get('T016', []))
    print(f'Generated {total_features} features ({primary_count} primary + {derived_count} derived)')
    print(f'Code size: {len(code)} chars')

    # 写入文件
    save_feature_calculator(code)
    print('Saved to outputs/feature_code/features_calculator_v2.py')

    # 验证语法
    try:
        compile(code, 'features_calculator_v2.py', 'exec')
        print('Syntax check: OK')
    except SyntaxError as e:
        print(f'Syntax error: {e}')

    # 验证T016引用完整性
    try:
        _validate_t016_references(PARAM_COMBOS.get('T016', []), PARAM_COMBOS)
        print('T016 reference validation: PASSED')
    except ValueError as e:
        print(f'T016 reference validation: FAILED')
        print(e)

