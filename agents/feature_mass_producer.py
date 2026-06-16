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
from copy import deepcopy
from itertools import product
from typing import Dict, List, Tuple, Optional

try:
    import numpy as np
except ModuleNotFoundError:
    np = None

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


BUILTIN_TEMPLATE_MAX_NUMBER = 16
DYNAMIC_TEMPLATE_MAX_COMBOS = 48
PARAM_COMBOS = _build_param_combos()


def _template_number(template_id: str) -> Optional[int]:
    if not template_id or not template_id.startswith('T'):
        return None
    suffix = template_id[1:]
    return int(suffix) if suffix.isdigit() else None


def is_builtin_template_id(template_id: str) -> bool:
    number = _template_number(template_id)
    return number is not None and number <= BUILTIN_TEMPLATE_MAX_NUMBER


def _template_field(template, field: str, default=None):
    if isinstance(template, dict):
        return template.get(field, default)
    return getattr(template, field, default)


def _function_name(value: str) -> str:
    if not value:
        return ''
    return value.split('(', 1)[0].strip()


def _function_param_names(value: str) -> List[str]:
    if not value or '(' not in value:
        return []
    inside = value.split('(', 1)[1].rsplit(')', 1)[0]
    names = []
    for part in inside.split(','):
        token = part.strip()
        if not token or token in ('*', '/'):
            continue
        token = token.split(':', 1)[0].split('=', 1)[0].strip()
        if token and token not in ('data', 'apply_time_dt', 'self'):
            names.append(token)
    return names


def _is_dynamic_template_params(params: Dict) -> bool:
    return bool(params.get('__dynamic_template'))


def _spec_values(spec) -> List:
    if not isinstance(spec, dict):
        return []
    for key in ('values', 'enum', 'options', 'choices'):
        values = spec.get(key)
        if isinstance(values, list):
            return values
    return []


def _dynamic_values_for_param(name: str, spec: Dict, all_names: set) -> List:
    explicit = _spec_values(spec)
    if explicit:
        return explicit
    if name == 'source':
        if 'value_field' in all_names:
            return ['fdc_pinjaman']
        return ['applist', 'fdc_pinjaman']
    if name in ('window', 'window_days'):
        if 'value_field' in all_names:
            return [30, 90, 180]
        return [7, 30, 90]
    if name == 'value_field':
        return ['nilai_pendanaan', 'sisa_pinjaman_berjalan', 'pendapatan']
    if name == 'method':
        return ['sum', 'mean', 'max', 'min'] if 'value_field' in all_names else ['mean']
    if name == 'decay_type':
        return ['exponential', 'linear']
    if name == 'half_life_days':
        return [7.0, 15.0]
    if name == 'weight_field':
        return [None]
    if name == 'min_count':
        return [1]
    if name == 'cond':
        return [None]
    if name == 'time_field':
        return ['inTime', 'tgl_penyaluran_dana']
    default = spec.get('default') if isinstance(spec, dict) else None
    return [default] if default is not None else []


def _normalize_dynamic_param_name(name: str, function_params: set) -> str:
    if name == 'window' and 'window_days' in function_params:
        return 'window_days'
    return name


def _dynamic_template_param_combos(template) -> List[Dict]:
    """Expand project-enabled T017+ templates from their own parameter_space."""
    tid = _template_field(template, 'template_id', '')
    template_name = _template_field(template, 'template_name', '')
    python_function_raw = _template_field(template, 'python_function', '')
    python_function = _function_name(python_function_raw)
    if not python_function:
        return []

    parameter_space = _template_field(template, 'parameter_space', {}) or {}
    function_params = set(_function_param_names(python_function_raw))
    param_specs = []
    for raw_name, spec in parameter_space.items():
        name = _normalize_dynamic_param_name(raw_name, function_params)
        if name in ('data', 'apply_time_dt', 'self'):
            continue
        values = _dynamic_values_for_param(raw_name, spec, set(parameter_space.keys()))
        if not values:
            continue
        param_specs.append((name, values))

    if not param_specs:
        param_specs = [(name, _dynamic_values_for_param(name, {}, function_params)) for name in sorted(function_params)]
        param_specs = [(name, values) for name, values in param_specs if values]

    combos = []
    for values in product(*(item[1] for item in param_specs)):
        combo = dict(zip((item[0] for item in param_specs), values))
        if 'window_days' in combo:
            combo['window'] = combo['window_days']
        combo['__dynamic_template'] = True
        combo['__template_id'] = tid
        combo['__template_name'] = template_name
        combo['__python_function'] = python_function
        combo['__formula_template'] = _template_field(template, 'formula_template', '')
        combos.append(combo)
        if len(combos) >= DYNAMIC_TEMPLATE_MAX_COMBOS:
            break
    return combos


def build_param_combos(extra_templates: List = None) -> Dict[str, List[Dict]]:
    """Return active param combos for one generation run.

    T001-T016 are built-in. T017+ must come from the active template library and,
    for project runs, from templates explicitly enabled by the project.
    """
    combos = deepcopy(PARAM_COMBOS)
    for template in extra_templates or []:
        tid = _template_field(template, 'template_id', '')
        if not tid or is_builtin_template_id(tid):
            continue
        dynamic = _dynamic_template_param_combos(template)
        if dynamic:
            combos[tid] = dynamic
    return combos


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

    elif _is_dynamic_template_params(params):
        prefix = ''.join(part[0] for part in params.get('__template_name', tid.lower()).split('_') if part) or tid.lower()
        parts = [prefix]
        if params.get('source'):
            parts.append(_short_source(params['source']))
        if params.get('value_field'):
            parts.append(params.get('vf_label') or params['value_field'])
        if params.get('method'):
            parts.append(params['method'])
        if params.get('decay_type'):
            parts.append({'exponential': 'exp', 'linear': 'lin', 'step': 'step'}.get(params['decay_type'], params['decay_type']))
        if params.get('half_life_days') is not None:
            parts.append('h' + str(params['half_life_days']).replace('.', 'x'))
        window = params.get('window') or params.get('window_days')
        if window:
            parts.append(f"{window}d")
        return '_'.join(str(p).replace('.', 'x') for p in parts)

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
    if _is_dynamic_template_params(params):
        return params.get('__python_function', 'calc_count')
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
    elif _is_dynamic_template_params(params):
        return {
            key: value
            for key, value in params.items()
            if not key.startswith('__') and key != 'window' and value is not None
        }
    return {}


def _source_label(source: str) -> str:
    """Return a Chinese data-domain label for report exports."""
    labels = {
        'applist': 'APP安装列表',
        'fdc_inquiry': 'FDC征信查询统计',
        'fdc_pinjaman': 'FDC贷款记录',
        'base': '用户基础信息',
    }
    return labels.get(source, source or '衍生特征')


def _source_path(source: str) -> str:
    paths = {
        'applist': 'params.appList[]',
        'fdc_inquiry': 'params.FDC.history_inquiry',
        'fdc_pinjaman': 'params.FDC.pinjaman[]',
        'base': 'params.base',
    }
    return paths.get(source, source or 'derived')


def _field_label(field: str) -> str:
    labels = {
        'inTime': '安装时间',
        'upTime': '更新时间',
        'packageX': 'APP包名',
        'category': 'APP分类',
        'hit_by': '查询机构',
        'tgl_inquiry': '查询时间',
        'jml_data': '查询命中数据量',
        'tgl_penyaluran_dana': '放款日期',
        'id_penyelenggara': '放贷机构ID',
        'tipe_pinjaman': '贷款类型',
        'status_pinjaman': '贷款状态',
        'kualitas_pinjaman': '贷款质量等级',
        'nilai_pendanaan': '放款金额',
        'sisa_pinjaman_berjalan': '在贷余额',
        'pendapatan': 'FDC记录收入',
        'pendanaan_syariah': '是否伊斯兰金融',
        'salary': '申请填写月收入',
        'birthday': '生日',
        'workYears': '工作年限',
        'gender': '性别',
        'marita': '婚姻状态',
        'children': '子女数',
        'job': '职业代码',
        'device_id': '设备ID',
    }
    return labels.get(field, field)


def _category_label(category: str) -> str:
    labels = {
        'gambling': '赌博类APP',
        'cash_loan': '现金贷类APP',
        'fintech_lending': '金融借贷类APP',
        'fake_gps': '虚拟定位类APP',
        'clone_app': '应用克隆类APP',
        'banking': '银行类APP',
        'ewallet': '电子钱包类APP',
        'shopping': '购物类APP',
        'food_delivery': '外卖配送类APP',
    }
    return labels.get(category, category)


def _field_ref(source: str, field: str) -> str:
    if source == 'applist':
        return f"appList[].{field}"
    if source == 'fdc_pinjaman':
        return f"pinjaman[].{field}"
    if source == 'fdc_inquiry':
        if field.startswith('statistic.'):
            return f"history_inquiry.{field}"
        return f"last3DaysInquiry[].{field}"
    if source == 'base':
        return f"base.{field}"
    return field


def _field_desc(source: str, fields: List[str]) -> str:
    unique_fields = []
    for field in fields:
        if field and field not in unique_fields:
            unique_fields.append(field)
    return '、'.join(
        f"{_field_ref(source, field)}（{_field_label(field.split('.')[-1])}）"
        for field in unique_fields
    )


def _data_source_text(source: str, fields: List[str]) -> str:
    fields_text = _field_desc(source, fields)
    if fields_text:
        return f"{_source_label(source)}（{_source_path(source)}）；涉及字段：{fields_text}"
    return f"{_source_label(source)}（{_source_path(source)}）"


def _format_cond(cond: Optional[Dict]) -> str:
    if not cond:
        return ''
    return ' 且 '.join(f"{k}={repr(v)}（{_field_label(k)}）" for k, v in cond.items())


def _format_formula_cond(cond: Optional[Dict], source: str = '') -> str:
    if not cond:
        return ''
    return ' AND '.join(f"{_field_ref(source, k)}={repr(v)}" for k, v in cond.items())


def _format_category_list(categories: List[str]) -> str:
    return '、'.join(_category_label(c) for c in categories)


def _feature_data_source(tid: str, params: Dict) -> str:
    if tid == 'T001':
        source = params.get('source', '')
        fields = ['tgl_penyaluran_dana'] if source == 'fdc_pinjaman' else ['inTime', 'upTime']
        if source == 'fdc_inquiry':
            fields = [f"statistic.{params.get('window')}_hari"]
        fields.extend((params.get('cond') or {}).keys())
        return _data_source_text(source, fields)
    if tid == 'T002':
        source = params.get('source', '')
        fields = ['tgl_penyaluran_dana', params.get('dedup_field')] if source == 'fdc_pinjaman' else [params.get('dedup_field')]
        if source == 'fdc_inquiry':
            fields = ['last3DaysInquiry', 'tgl_inquiry', params.get('dedup_field')]
        return _data_source_text(source, fields)
    if tid == 'T003':
        source = params.get('source', '')
        return _data_source_text(source, ['tgl_penyaluran_dana', params.get('value_field')])
    if tid in ('T007', 'T008', 'T009'):
        source = params.get('source', '')
        if source == 'fdc_pinjaman':
            return _data_source_text(source, ['tgl_penyaluran_dana'])
        if source == 'fdc_inquiry':
            return _data_source_text(source, ['statistic.*_hari'])
        return _data_source_text(source, ['inTime', 'upTime'])
    if tid == 'T004':
        if params.get('use_by_category'):
            cats = '、'.join(_category_label(c) for c in params.get('allowed_categories', []))
            return (
                "APP安装列表（params.appList[]）+ APP分类映射；"
                f"涉及字段：appList[].inTime（安装时间）、appList[].upTime（更新时间）、"
                f"appList[].packageX（APP包名）、classification[packageX].category（APP分类，目标类别：{cats}）"
            )
        source = params.get('source', '')
        return _data_source_text(source, ['tgl_penyaluran_dana', *(params.get('target_cond') or {}).keys()])
    if tid == 'T005':
        if params.get('use_by_category'):
            return (
                "APP安装列表（params.appList[]）+ APP分类映射；"
                "涉及字段：appList[].inTime（安装时间）、appList[].packageX（APP包名）、"
                "classification[packageX].category（APP分类）"
            )
        source = params.get('source', '')
        return _data_source_text(source, ['tgl_penyaluran_dana', params.get('category_field')])
    if tid == 'T006':
        source_a = params.get('source_a', '')
        source_b = params.get('source_b', '')
        return (
            f"{_source_label(source_a)}（{_source_path(source_a)}）+ {_source_label(source_b)}（{_source_path(source_b)}）；"
            f"涉及字段：{_field_ref(source_a, params.get('field_a', ''))}（{_field_label(params.get('field_a', ''))}）、"
            f"{_field_ref(source_b, params.get('field_b', ''))}（{_field_label(params.get('field_b', ''))}）"
        )
    if tid in ('T010', 'T011'):
        metric = params.get('target_metric', '')
        if metric == 'salary':
            return "用户基础信息（params.base）+ 训练集参考分布；涉及字段：base.salary（申请填写月收入）"
        if metric == 'loan_amount':
            return "FDC贷款记录（params.FDC.pinjaman[]）+ 训练集参考分布；涉及字段：pinjaman[].nilai_pendanaan（放款金额）"
        if metric == 'inquiry_count':
            return "FDC征信查询统计（params.FDC.history_inquiry）+ 训练集参考分布；涉及字段：history_inquiry.statistic.30_hari（近30天查询次数）"
        if metric == 'applist_count':
            return "APP安装列表（params.appList[]）+ 训练集参考分布；涉及字段：appList[]（安装APP数量）"
        return "样本当前值 + 训练集参考分布"
    if tid == 'T012':
        metric = params.get('target_metric', '')
        if metric == 'app_install_pattern':
            return "APP安装列表（params.appList[]）+ 训练集参考矩阵；涉及字段：appList[]（APP总数）、appList[].sysApp（系统APP标识）"
        if metric == 'loan_pattern':
            return "FDC贷款记录（params.FDC.pinjaman[]）+ 训练集参考矩阵；涉及字段：pinjaman[].nilai_pendanaan（放款金额）、pinjaman[].id_penyelenggara（放贷机构ID）"
        return "当前样本特征向量 + 训练集参考矩阵"
    if tid == 'T013':
        return (
            "用户基础信息（params.base）+ FDC贷款记录（params.FDC.pinjaman[]）；"
            f"涉及字段：{params.get('declared_field')}（申报字段）、{params.get('actual_field')}（实际字段）"
        )
    if tid == 'T014':
        pairs = params.get('field_pairs_config', [])
        fields = []
        for pair in pairs:
            if pair.get('src') and pair.get('field'):
                fields.append(f"{pair.get('src')}.{pair.get('field')}")
        return f"跨数据源一致性校验；涉及字段：{', '.join(fields) if fields else 'field_pairs'}"
    if tid == 'T015':
        shared = params.get('shared_field', '')
        if shared == 'packageX':
            return "设备关联APP聚类；涉及字段：device_id（设备ID）、appList[].packageX（APP包名）"
        if shared == 'id_penyelenggara':
            return "设备关联FDC放贷机构聚类；涉及字段：device_id（设备ID）、pinjaman[].id_penyelenggara（放贷机构ID）"
        return f"device_id + {shared}"
    if _is_dynamic_template_params(params):
        source = params.get('source', '')
        fields = []
        if source == 'fdc_pinjaman':
            fields.append('tgl_penyaluran_dana')
        elif source == 'applist':
            fields.extend(['inTime', 'upTime'])
        for field_key in ('value_field', 'weight_field', 'time_field'):
            if params.get(field_key):
                fields.append(params[field_key])
        fields.extend((params.get('cond') or {}).keys())
        return _data_source_text(source, fields)
    if tid == 'T016':
        refs = [
            params.get('ref_feature_name'),
            params.get('ref_feature_a'),
            params.get('ref_feature_b'),
            params.get('ref_feature_short'),
            params.get('ref_feature_long'),
        ]
        refs = [r for r in refs if r]
        return f"衍生特征；涉及上游特征：{', '.join(refs)}" if refs else '衍生特征'
    return '未知数据来源'


def _feature_formula(tid: str, params: Dict) -> str:
    """Chinese calculation logic that mirrors generated code."""
    if tid == 'T001':
        source = params['source']
        window = params['window']
        cond = _format_cond(params.get('cond'))
        cond_formula = _format_formula_cond(params.get('cond'), source)
        where_text = f"，并满足 {cond}" if cond else ''
        where_formula = f" AND {cond_formula}" if cond_formula else ''
        time_field = 'tgl_penyaluran_dana' if source == 'fdc_pinjaman' else 'inTime'
        if source == 'fdc_inquiry':
            return (
                f"统计申请时间前{window}天内的FDC查询次数。"
                f"公式：history_inquiry.statistic['{window}_hari']"
            )
        return (
            f"统计申请时间前{window}天内，{_source_label(source)}的记录数量{where_text}。"
            f"公式：COUNT({_source_path(source)} WHERE {_field_ref(source, time_field)} ∈ (applyTime-{window}天, applyTime]{where_formula})"
        )
    if tid == 'T002':
        source = params['source']
        window = params['window']
        field = params['dedup_field']
        return (
            f"统计申请时间前{window}天内，{_source_label(source)}中{_field_label(field)}的去重数量。"
            f"公式：COUNT_DISTINCT({_field_ref(source, field)} WHERE 时间 ∈ (applyTime-{window}天, applyTime])"
        )
    if tid == 'T003':
        source = params['source']
        window = params['window']
        vf = params.get('value_field') or 'event'
        return (
            f"对申请时间前{window}天内的{_source_label(source)}按时间衰减加权求和，越近记录权重越高。"
            f"公式：SUM({_field_ref(source, vf)} * {params['decay_func']}_decay(applyTime-{_field_ref(source, 'tgl_penyaluran_dana')}, rate={params['decay_rate']}))"
        )
    if tid == 'T004':
        if params.get('use_by_category'):
            window = params['window']
            cats = params.get('allowed_categories', [])
            cats_cn = _format_category_list(cats)
            cats_formula = ','.join(cats)
            return (
                f"计算申请时间前{window}天内，{cats_cn}安装量占全部安装APP数量的比例。"
                f"公式：COUNT(appList WHERE inTime ∈ (applyTime-{window}天, applyTime] AND category(packageX) IN [{cats_formula}]) / "
                f"COUNT(appList WHERE inTime ∈ (applyTime-{window}天, applyTime])"
            )
        source = params['source']
        window = params['window']
        cond = _format_cond(params.get('target_cond'))
        cond_formula = _format_formula_cond(params.get('target_cond'), source)
        return (
            f"计算申请时间前{window}天内，{_source_label(source)}中满足 {cond} 的记录占全部记录的比例。"
            f"公式：COUNT({_source_path(source)} WHERE 时间 ∈ (applyTime-{window}天, applyTime] AND {cond_formula}) / "
            f"COUNT({_source_path(source)} WHERE 时间 ∈ (applyTime-{window}天, applyTime])"
        )
    if tid == 'T005':
        if params.get('use_by_category'):
            return (
                f"衡量申请时间前{params['window']}天内APP分类分布的集中度。"
                f"公式：{params['method']}(category(packageX) distribution of appList in last {params['window']} days)"
            )
        source = params['source']
        field = params['category_field']
        return (
            f"衡量申请时间前{params['window']}天内{_source_label(source)}按{_field_label(field)}分布的集中度。"
            f"公式：{params['method']}({_field_ref(source, field)} distribution in last {params['window']} days)"
        )
    if tid == 'T006':
        source_a = params['source_a']
        source_b = params['source_b']
        return (
            f"计算申请时间前{params['window']}天内两个数据源指定字段集合的重叠度。"
            f"公式：JACCARD(SET({_field_ref(source_a, params['field_a'])}), SET({_field_ref(source_b, params['field_b'])}))"
        )
    if tid == 'T007':
        src = params['source']
        s = params['short_window']
        l = params['long_window']
        return (
            f"比较{_source_label(src)}短窗口{s}天与长窗口{l}天的日均数量变化，识别近期加速。"
            f"公式：(COUNT({s}天)/{s}) / (COUNT({l}天)/{l}) - 1"
        )
    if tid == 'T008':
        src = params['source']
        wins = ','.join(f"{w}d" for w in params['windows'])
        return (
            f"用多个时间窗口的日均数量拟合趋势斜率，衡量{_source_label(src)}近期变化方向。"
            f"公式：SLOPE([COUNT(w)/w for w in {wins}])"
        )
    if tid == 'T009':
        src = params['source']
        return (
            f"检测申请时间前{params['window']}天内{_source_label(src)}是否存在单日突增。"
            f"公式：MAX_DAILY_COUNT({params['window']}天) / AVG_DAILY_COUNT({params['window']}天)，低于阈值{params['threshold']}则记0"
        )
    if tid == 'T010':
        return f"计算当前样本 {params['target_metric']} 在训练集参考分布中的百分位。公式：PERCENT_RANK(value, reference_distribution)"
    if tid == 'T011':
        return f"计算当前样本 {params['target_metric']} 相对训练集均值的标准差偏离。公式：(value - reference_mean) / reference_std"
    if tid == 'T012':
        return f"计算当前样本 {params['target_metric']} 向量相对训练集参考矩阵的异常度。公式：ANOMALY_SCORE(vector, reference_matrix, method={params.get('method', 'mahalanobis')})"
    if tid == 'T013':
        return (
            f"比较用户申报字段与FDC实际字段的一致性。"
            f"公式：{params['method']}({params['declared_field']}, {params['actual_field']})"
        )
    if tid == 'T014':
        pairs = params.get('field_pairs_config', [])
        fields = ', '.join(f"{p.get('src')}.{p.get('field')}" for p in pairs)
        return f"计算跨数据源字段不一致程度。公式：CROSS_SOURCE_DISCREPANCY({fields})"
    if tid == 'T015':
        return (
            f"统计同一{_field_label(params['identity_field'])}关联的{_field_label(params['shared_field'])}去重数量。"
            f"公式：COUNT_DISTINCT({params['shared_field']} GROUP BY {params['identity_field']})"
        )
    if _is_dynamic_template_params(params):
        template = params.get('__template_name') or tid
        formula = params.get('__formula_template') or ''
        for key, value in params.items():
            if key.startswith('__') or value is None:
                continue
            formula = formula.replace('{' + key + '}', str(value))
        visible_params = {
            key: value
            for key, value in params.items()
            if not key.startswith('__') and key != 'window' and value is not None
        }
        if formula:
            return f"按项目启用模板 {template} 计算。公式：{formula}"
        return f"按项目启用模板 {template} 调用 {params.get('__python_function')}，参数：{visible_params}"
    if tid == 'T016':
        dtype = params.get('derived_type', '')
        if dtype == 'ratio_density':
            return f"把上游计数特征换算为日均密度。公式：{params['ref_feature_name']} / {params['window']}"
        if dtype == 'ratio_cross':
            return f"计算两个上游特征的比值。公式：{params['ref_feature_a']} / {params['ref_feature_b']}"
        if dtype == 'weighted_combo':
            label = params.get('label', 'weighted_combo')
            return (
                f"加权组合 = Σ(w_i × feature_i)，各维度权重由风险重要性确定（如{label}的综合评分）。"
                f"当前实现使用两个上游风险信号构造风险暴露交互项：{params['ref_feature_a']} × {params['ref_feature_b']}"
            )
        if dtype == 'extended_velocity':
            return (
                f"比较短窗口和长窗口的日均变化速度。公式：({params['ref_feature_short']} / {params['short_window']}) / "
                f"({params['ref_feature_long']} / {params['long_window']}) - 1"
            )
        if dtype == 'squared':
            return f"放大上游特征的非线性高值影响。公式：{params['ref_feature_name']} ** 2"
        if dtype == 'log_transform':
            return f"对上游特征做对数平滑，降低极端值影响。公式：LOG({params['ref_feature_name']} + 1)"
        if dtype == 'difference':
            return f"计算两个上游特征的差值。公式：{params['ref_feature_a']} - {params['ref_feature_b']}"
        if dtype == 'is_high':
            return f"把上游特征转为高风险命中标记。公式：1 if {params['ref_feature_name']} > 0 else 0"
    return tid


def get_feature_metadata_map(param_combos: Dict[str, List[Dict]] = None) -> Dict[str, Dict[str, str]]:
    """Build feature-name metadata for report/CSV export.

    The mass-production path is deterministic, so the generated feature name can
    be mapped back to its template ID, data source, and calculation logic without
    calling an LLM.
    """
    param_combos = param_combos or PARAM_COMBOS
    metadata = {}
    derived_refs = {}
    for tid, combos_list in param_combos.items():
        for params in combos_list:
            name = _generate_feature_name(tid, params)
            metadata[name] = {
                'feature_name': name,
                'template_id': tid,
                'data_source': _feature_data_source(tid, params),
                'calculation_logic': _feature_formula(tid, params),
            }
            if tid == 'T016':
                refs = [
                    params.get('ref_feature_name'),
                    params.get('ref_feature_a'),
                    params.get('ref_feature_b'),
                    params.get('ref_feature_short'),
                    params.get('ref_feature_long'),
                ]
                refs = [r for r in refs if r]
                if refs:
                    derived_refs[name] = refs

    for name, refs in derived_refs.items():
        upstream_sources = []
        for ref in refs:
            ref_source = metadata.get(ref, {}).get('data_source')
            if ref_source:
                upstream_sources.append(f"{ref}：{ref_source}")
            else:
                upstream_sources.append(ref)
        metadata[name]['data_source'] = (
            f"衍生特征；涉及上游特征：{', '.join(refs)}；"
            f"上游字段来源：{'；'.join(upstream_sources)}"
        )
    return metadata


def get_feature_metadata(feature_name: str) -> Dict[str, str]:
    """Return metadata for one generated feature name."""
    return get_feature_metadata_map().get(feature_name, {})


def save_feature_metadata(output_path: str = None, param_combos: Dict[str, List[Dict]] = None) -> str:
    """Persist feature metadata generated from the same template combos as code.

    This file is the stable handoff between feature generation, evaluation, and
    report export. Downstream CSV/report code should prefer this artifact over
    importing the generator directly.
    """
    if output_path is None:
        output_path = 'outputs/feature_code/feature_metadata.json'
    metadata = get_feature_metadata_map(param_combos=param_combos)
    payload = {
        'total_features': len(metadata),
        'features': metadata,
    }
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return output_path


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
    if np is None:
        raise RuntimeError("numpy is required to precompute reference distributions")

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
    if _is_dynamic_template_params(params):
        return params.get('__python_function', 'calc_count')
    if tid == 'T004':
        return 'calc_proportion_by_category' if params.get('use_by_category') else 'calc_proportion'
    if tid == 'T005':
        return 'calc_concentration_by_category' if params.get('use_by_category') else 'calc_concentration'
    if tid == 'T016':
        return None  # T016 is pure arithmetic, no import needed
    return tid_func_map.get(tid, 'calc_count')


def _collect_func_names(param_combos: Dict[str, List[Dict]] = None) -> List[str]:
    """收集所有需要的计算函数名"""
    param_combos = param_combos or PARAM_COMBOS
    names = set()
    for tid, combos_list in param_combos.items():
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
    elif _is_dynamic_template_params(params):
        for key, value in params.items():
            if key.startswith('__') or key == 'window' or value is None:
                continue
            parts.append(f"{key}={repr(value)}")
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


def _compose_code(total_features: int, param_combos: Dict[str, List[Dict]] = None) -> str:
    """组合生成完整的FeatureCalculator类代码"""
    param_combos = param_combos or PARAM_COMBOS
    func_names = _collect_func_names(param_combos)

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
    for tid in sorted(param_combos.keys()):
        if tid == 'T016':
            continue  # T016 derived features are computed in a separate block
        combos_list = param_combos[tid]
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
    if 'T016' in param_combos:
        lines.append('        # ===== Derived Features (T016) =====')
        for params in param_combos['T016']:
            fname = _generate_feature_name('T016', params)
            code_line = _compose_T016(params)
            lines.append(f'        # {fname}')
            lines.append(code_line)
            lines.append('')

    # return语句
    last_tid = sorted(param_combos.keys())[-1]
    lines.append('        return {')
    for tid in sorted(param_combos.keys()):
        combos_list = param_combos[tid]
        for i, params in enumerate(combos_list):
            fname = _generate_feature_name(tid, params)
            is_last = tid == last_tid and i == len(combos_list) - 1
            comma = '' if is_last else ','
            lines.append(f"            '{fname}': {fname}{comma}")
    lines.append('        }')

    return '\n'.join(lines)


def produce_all_features(ref_distributions: Dict = None, param_combos: Dict[str, List[Dict]] = None) -> str:
    """生成完整的特征计算代码

    Args:
        ref_distributions: 预计算的参考分布

    Returns:
        完整的Python代码
    """
    param_combos = param_combos or PARAM_COMBOS
    total = sum(len(combos) for combos in param_combos.values())
    code = _compose_code(total, param_combos)
    return code


def save_feature_calculator(code: str, output_path: str = None, param_combos: Dict[str, List[Dict]] = None) -> str:
    """将生成的代码写入文件"""
    if output_path is None:
        output_path = 'outputs/feature_code/features_calculator_v2.py'
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(code)
    save_feature_metadata(param_combos=param_combos)
    return output_path


def save_reference_distributions(refs: Dict, output_path: str = None) -> str:
    """保存参考分布到JSON"""
    if output_path is None:
        output_path = 'outputs/feature_code/reference_distributions.json'
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    clean = {}
    for k, v in refs.items():
        if np is not None and isinstance(v, np.ndarray):
            clean[k] = v.tolist()
        elif np is not None and isinstance(v, (np.floating,)):
            clean[k] = float(v)
        elif np is not None and isinstance(v, (np.integer,)):
            clean[k] = int(v)
        elif isinstance(v, list):
            vals = []
            for item in v:
                if np is not None and isinstance(item, np.ndarray):
                    vals.append(item.tolist())
                elif np is not None and isinstance(item, (np.floating, np.integer)):
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
