import json
import os
import re
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional


class FeatureCalculator:
    def __init__(self):
        self.app_classification_cache = self._load_app_cache()
        # 预定义分类集合，便于快速匹配
        self.LOAN_CATS = {'cash_loan', 'fintech_lending', 'p2p'}
        self.HIGH_RISK_CATS = {'gambling', 'fake_gps', 'clone_app'}
        self.SUSPICIOUS_PATTERNS = ['generic_name', 'non_standard_domain', 'obfuscated']
        self.STANDARD_CATS = [
            'gambling', 'cash_loan', 'fintech_lending', 'banking', 'ewallet',
            'installment', 'app_store', 'fake_gps', 'clone_app', 'shopping',
            'food_delivery', 'transportation', 'utility', 'productivity',
            'religious', 'social_entertainment', 'other'
        ]

    def _load_app_cache(self) -> Dict:
        cache_file = 'outputs/app_analysis/classification_complete_11850.json'
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('classifications', {})
        return {}

    def _safe_parse_date(self, date_str: str, fmt: str = '%Y-%m-%d') -> Optional[datetime]:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except Exception:
            return None

    def _get_category(self, package_x: str) -> str:
        if package_x in self.app_classification_cache:
            return self.app_classification_cache[package_x].get('category', 'other')
        return 'other'

    def calculate_all(self, data: Dict, apply_time: str = None) -> Dict:
        # 1. 提取申请时间（防时间穿越基准）
        if not apply_time:
            apply_time_ms = data.get('applyTime', 0)
            if apply_time_ms:
                apply_time_dt = datetime.fromtimestamp(apply_time_ms / 1000)
            else:
                apply_time_dt = datetime.now()
        else:
            apply_time_dt = datetime.strptime(apply_time, '%Y-%m-%d %H:%M:%S')

        # 2. 过滤数据（严格防时间穿越）
        filtered_applist = self._filter_applist(data, apply_time_dt)
        filtered_fdc = self._filter_fdc(data, apply_time_dt)

        # 3. 计算各模块特征
        features = {}
        features.update(self._calc_applist_features(filtered_applist, apply_time_dt))
        features.update(self._calc_fdc_features(filtered_fdc, data, apply_time_dt))
        features.update(self._calc_base_features(data, apply_time_dt))

        return features

    def _filter_applist(self, data: Dict, apply_time_dt: datetime) -> List[Dict]:
        app_list = data.get('params', {}).get('appList', [])
        apply_time_ms = apply_time_dt.timestamp() * 1000
        # 仅保留安装时间 <= 申请时间的记录
        return [app for app in app_list if app.get('inTime', 0) <= apply_time_ms]

    def _filter_fdc(self, data: Dict, apply_time_dt: datetime) -> Dict:
        import copy
        fdc = copy.deepcopy(data.get('params', {}).get('FDC', {}))
        if 'pinjaman' in fdc:
            filtered = []
            for loan in fdc['pinjaman']:
                disburse_str = loan.get('tgl_penyaluran_dana', '')
                if disburse_str:
                    disburse_dt = self._safe_parse_date(disburse_str)
                    if disburse_dt and disburse_dt <= apply_time_dt:
                        filtered.append(loan)
                    elif not disburse_dt:
                        filtered.append(loan)  # 无法解析则保留，交由后续逻辑处理
                else:
                    filtered.append(loan)
            fdc['pinjaman'] = filtered
        return fdc

    def _calc_applist_features(self, filtered_applist: List[Dict], apply_time_dt: datetime) -> Dict:
        features = {}
        if not filtered_applist:
            return {k: 0 for k in [
                'ratio_applist_loandensity_30d', 'ratio_applist_loandensity_90d', 'ratio_applist_loandensity_180d',
                'flag_applist_loandensity_high_30d', 'count_applist_activeloadapp_7d', 'count_applist_activeloadapp_30d',
                'flag_applist_activeloadapp_high_7d', 'ratio_applist_veruniformity_all', 'flag_applist_veruniformity_high_all',
                'ratio_applist_veruniformity_custom_90d', 'count_applist_shortinstall_7d', 'count_applist_shortinstall_3d',
                'flag_applist_shortinstall_high_7d', 'ratio_applist_highriskdensity_all', 'ratio_applist_highriskdensity_90d',
                'flag_applist_highriskdensity_high_all', 'ratio_applist_diversityindex_all', 'ratio_applist_diversityindex_180d',
                'flag_applist_diversityindex_low_all', 'count_applist_suspiciouspkg_all', 'count_applist_suspiciouspkg_30d',
                'flag_applist_suspiciouspkg_high_all', 'count_applist_updatefreq_30d', 'count_applist_updatefreq_7d',
                'flag_applist_updatefreq_high_30d'
            ]}

        # 预计算分类映射
        app_cats = {app.get('packageX', ''): self._get_category(app.get('packageX', '')) for app in filtered_applist}
        apply_time_ms = apply_time_dt.timestamp() * 1000

        # 辅助函数：按时间窗口过滤
        def filter_window(field: str, days: int):
            cutoff = (apply_time_dt - timedelta(days=days)).timestamp() * 1000
            return [app for app in filtered_applist if app.get(field, 0) >= cutoff]

        # 1. 贷款密度 (30d/90d/180d)
        for days, suffix in [(30, '30d'), (90, '90d'), (180, '180d')]:
            window_apps = filter_window('inTime', days)
            total = len(window_apps)
            loan_count = sum(1 for a in window_apps if app_cats.get(a.get('packageX', '')) in self.LOAN_CATS)
            features[f'ratio_applist_loandensity_{suffix}'] = loan_count / total if total > 0 else 0.0

        # 2. 贷款密度高标记 (30d)
        ld30 = features['ratio_applist_loandensity_30d']
        count_30d = len(filter_window('inTime', 30))
        features['flag_applist_loandensity_high_30d'] = 1 if ld30 > 0.15 and count_30d > 30 else 0

        # 3. 活跃贷款APP (7d/30d)
        for days, suffix in [(7, '7d'), (30, '30d')]:
            window_apps = filter_window('upTime', days)
            loan_apps = [a for a in window_apps if app_cats.get(a.get('packageX', '')) in self.LOAN_CATS]
            features[f'count_applist_activeloadapp_{suffix}'] = len({a.get('appName') for a in loan_apps if a.get('appName')})

        features['flag_applist_activeloadapp_high_7d'] = 1 if features['count_applist_activeloadapp_7d'] >= 3 else 0

        # 4. 版本一致性 (全量/90d)
        all_loan = [a for a in filtered_applist if app_cats.get(a.get('packageX', '')) in self.LOAN_CATS]
        total_loan = len(all_loan)
        uniform_loan = sum(1 for a in all_loan if a.get('versionName') in ['standard', 'custom_build'])
        features['ratio_applist_veruniformity_all'] = uniform_loan / total_loan if total_loan > 0 else 0.0
        features['flag_applist_veruniformity_high_all'] = 1 if features['ratio_applist_veruniformity_all'] > 0.9 and total_loan > 15 else 0

        loan_90d = [a for a in filter_window('inTime', 90) if app_cats.get(a.get('packageX', '')) in self.LOAN_CATS]
        total_loan_90 = len(loan_90d)
        custom_loan_90 = sum(1 for a in loan_90d if a.get('versionName') == 'custom_build')
        features['ratio_applist_veruniformity_custom_90d'] = custom_loan_90 / total_loan_90 if total_loan_90 > 0 else 0.0

        # 5. 短期安装 (7d/3d)
        for days, suffix in [(7, '7d'), (3, '3d')]:
            window_apps = filter_window('inTime', days)
            features[f'count_applist_shortinstall_{suffix}'] = sum(1 for a in window_apps if app_cats.get(a.get('packageX', '')) in self.LOAN_CATS)
        features['flag_applist_shortinstall_high_7d'] = 1 if features['count_applist_shortinstall_7d'] >= 4 else 0

        # 6. 高风险密度 (全量/90d)
        total_pkg = len(filtered_applist)
        high_risk_all = sum(1 for a in filtered_applist if app_cats.get(a.get('packageX', '')) in self.HIGH_RISK_CATS)
        features['ratio_applist_highriskdensity_all'] = high_risk_all / total_pkg if total_pkg > 0 else 0.0

        apps_90d = filter_window('inTime', 90)
        total_90d = len(apps_90d)
        high_risk_90 = sum(1 for a in apps_90d if app_cats.get(a.get('packageX', '')) in self.HIGH_RISK_CATS)
        features['ratio_applist_highriskdensity_90d'] = high_risk_90 / total_90d if total_90d > 0 else 0.0
        features['flag_applist_highriskdensity_high_all'] = 1 if features['ratio_applist_highriskdensity_all'] > 0.2 else 0

        # 7. 多样性指数 (全量/180d)
        def calc_diversity(apps: List[Dict]):
            total = len(apps)
            if total == 0: return 0.0
            cat_counts = {}
            for a in apps:
                cat = app_cats.get(a.get('packageX', ''), 'other')
                cat_counts[cat] = cat_counts.get(cat, 0) + 1
            return 1.0 - sum((c / total) ** 2 for c in cat_counts.values())

        features['ratio_applist_diversityindex_all'] = calc_diversity(filtered_applist)
        features['ratio_applist_diversityindex_180d'] = calc_diversity(filter_window('inTime', 180))
        features['flag_applist_diversityindex_low_all'] = 1 if features['ratio_applist_diversityindex_all'] < 0.3 and features['ratio_applist_loandensity_30d'] > 0.4 else 0

        # 8. 可疑包名 (全量/30d)
        def is_suspicious(pkg: str) -> bool:
            pkg_lower = pkg.lower()
            return any(p in pkg_lower for p in self.SUSPICIOUS_PATTERNS)

        features['count_applist_suspiciouspkg_all'] = sum(1 for a in filtered_applist if is_suspicious(a.get('packageX', '')))
        apps_30d = filter_window('inTime', 30)
        features['count_applist_suspiciouspkg_30d'] = sum(1 for a in apps_30d if is_suspicious(a.get('packageX', '')))
        features['flag_applist_suspiciouspkg_high_all'] = 1 if features['count_applist_suspiciouspkg_all'] >= 5 else 0

        # 9. 更新频率 (30d/7d)
        update_cats = {'cash_loan', 'fintech_lending', 'utility', 'productivity', 'tool', 'security'}
        for days, suffix in [(30, '30d'), (7, '7d')]:
            window_apps = filter_window('upTime', days)
            features[f'count_applist_updatefreq_{suffix}'] = sum(1 for a in window_apps if app_cats.get(a.get('packageX', '')) in update_cats)
        features['flag_applist_updatefreq_high_30d'] = 1 if features['count_applist_updatefreq_30d'] >= 5 else 0

        return features

    def _calc_fdc_features(self, filtered_fdc: Dict, original_data: Dict, apply_time_dt: datetime) -> Dict:
        features = {}
        pinjaman = filtered_fdc.get('pinjaman', [])
        history_inq = filtered_fdc.get('history_inquiry', {})
        inquiry_records = filtered_fdc.get('inquiry_records', [])  # 假设存在进件明细记录

        # 辅助：按日期过滤贷款
        def filter_loans_window(days: int):
            cutoff = apply_time_dt - timedelta(days=days)
            return [l for l in pinjaman if self._safe_parse_date(l.get('tgl_penyaluran_dana', '')) and self._safe_parse_date(l.get('tgl_penyaluran_dana', '')) >= cutoff]

        # 辅助：按日期过滤进件记录
        def filter_inq_window(days: int):
            cutoff = apply_time_dt - timedelta(days=days)
            return [r for r in inquiry_records if self._safe_parse_date(r.get('tgl_inquiry', '')) and self._safe_parse_date(r.get('tgl_inquiry', '')) >= cutoff]

        # 1. 跨渠道重叠 (30d/90d)
        for days, suffix in [(30, '30d'), (90, '90d')]:
            inq_window = filter_inq_window(days)
            # 假设记录包含 channel_type 和 app_name
            channel_apps = {}
            for r in inq_window:
                ch = r.get('channel_type', 'unknown')
                app = r.get('app_name', '')
                if app:
                    channel_apps.setdefault(ch, set()).add(app)
            # 统计在不同channel重复出现的appName
            app_channels = {}
            for ch, apps in channel_apps.items():
                for a in apps:
                    app_channels.setdefault(a, set()).add(ch)
            overlap_count = sum(1 for chs in app_channels.values() if len(chs) > 1)
            features[f'count_fdc_crosschanneloverlap_{suffix}'] = overlap_count

        features['flag_fdc_crosschanneloverlap_high_30d'] = 1 if features['count_fdc_crosschanneloverlap_30d'] >= 3 else 0

        # 2. 查询激增比率
        last_7 = history_inq.get('last_7days', 0)
        last_30 = history_inq.get('last_30days', 0)
        last_3 = history_inq.get('last_3days', 0)
        last_90 = history_inq.get('last_90days', 0)
        avg_7 = last_7 / 7 if last_7 else 0
        avg_30 = last_30 / 30 if last_30 else 0
        avg_3 = last_3 / 3 if last_3 else 0
        avg_90 = last_90 / 90 if last_90 else 0

        features['ratio_fdc_inquiryspike_7d_vs_30d'] = (avg_7 / avg_30) if avg_30 > 0 else 0.0
        features['ratio_fdc_inquiryspike_3d_vs_90d'] = (avg_3 / avg_90) if avg_90 > 0 else 0.0
        features['flag_fdc_inquiryspike_extreme_7d'] = 1 if features['ratio_fdc_inquiryspike_7d_vs_30d'] > 3.0 else 0

        # 3. 独立机构数 (7d/30d)
        for days, suffix in [(7, '7d'), (30, '30d')]:
            inq_window = filter_inq_window(days)
            features[f'count_fdc_uniqueinst_{suffix}'] = len({r.get('id_penyelenggara') for r in inq_window if r.get('id_penyelenggara')})
        features['flag_fdc_uniqueinst_high_7d'] = 1 if features['count_fdc_uniqueinst_7d'] >= 5 else 0

        # 4. 查询转放款比率 (30d/90d)
        for days, suffix in [(30, '30d'), (90, '90d')]:
            loans_w = filter_loans_window(days)
            disb_count = sum(1 for l in loans_w if l.get('status_pinjaman') in ['O', 'L'])
            inq_count = len(filter_inq_window(days))
            features[f'ratio_fdc_inq2disb_{suffix}'] = disb_count / inq_count if inq_count > 0 else 0.0
        features['flag_fdc_inq2disb_low_30d'] = 1 if features['ratio_fdc_inq2disb_30d'] < 0.1 and len(filter_inq_window(30)) > 5 else 0

        # 5. 近期放款数 (30d/14d)
        for days, suffix in [(30, '30d'), (14, '14d')]:
            loans_w = filter_loans_window(days)
            features[f'count_fdc_recentdisb_{suffix}'] = sum(1 for l in loans_w if l.get('status_pinjaman') in ['O', 'X'])
        features['flag_fdc_recentdisb_high_30d'] = 1 if features['count_fdc_recentdisb_30d'] >= 3 else 0

        # 6. 查询到放款延迟 (30d/7d)
        for days, suffix in [(30, '30d'), (7, '7d')]:
            inq_w = filter_inq_window(days)
            # 简化匹配：假设进件记录与贷款记录可通过用户ID关联，此处按时间窗口内平均延迟估算
            lags = []
            for l in pinjaman:
                if l.get('status_pinjaman') == 'O':
                    dis_dt = self._safe_parse_date(l.get('tgl_penyaluran_dana', ''))
                    if dis_dt and (apply_time_dt - timedelta(days=days)) <= dis_dt <= apply_time_dt:
                        # 假设最近一次查询即为该笔贷款查询
                        lags.append(0) # 实际需关联ID，此处占位防报错
            features[f'avg_fdc_inq2disblag_{suffix}'] = sum(lags) / len(lags) if lags else 0.0
        features['flag_fdc_inq2disblag_short_30d'] = 1 if features['avg_fdc_inq2disblag_30d'] < 1 and sum(1 for l in pinjaman if l.get('status_pinjaman') == 'O' and self._safe_parse_date(l.get('tgl_penyaluran_dana', '')) and self._safe_parse_date(l.get('tgl_penyaluran_dana', '')) >= apply_time_dt - timedelta(days=30)) > 2 else 0

        # 7. 历史DPD均值 (180d/360d)
        weights = {'3': 1, '4': 2, '5': 3}
        for days, suffix in [(180, '180d'), (360, '360d')]:
            loans_w = filter_loans_window(days)
            valid = [l for l in loans_w if l.get('kualitas_pinjaman') in weights and l.get('status_pinjaman') in ['W', 'R', 'O']]
            if valid:
                weighted_sum = sum(float(l.get('dpd_max', 0)) * weights[l['kualitas_pinjaman']] for l in valid)
                features[f'avg_fdc_historicaldpd_{suffix}'] = weighted_sum / len(valid)
            else:
                features[f'avg_fdc_historicaldpd_{suffix}'] = 0.0
        severe_180 = [l for l in filter_loans_window(180) if l.get('kualitas_pinjaman') == '5']
        total_180 = len(filter_loans_window(180))
        features['flag_fdc_historicaldpd_severe_180d'] = 1 if features['avg_fdc_historicaldpd_180d'] > 60 and (len(severe_180) / total_180 if total_180 > 0 else 0) > 0.05 else 0

        # 8. 质量恶化比率 (90d/180d)
        for days, suffix in [(90, '90d'), (180, '180d')]:
            loans_w = filter_loans_window(days)
            degraded = sum(1 for l in loans_w if l.get('kualitas_pinjaman') in ['3', '4', '5'])
            outstanding = sum(1 for l in loans_w if l.get('status_pinjaman') == 'O')
            features[f'ratio_fdc_qualitydegrade_{suffix}'] = degraded / outstanding if outstanding > 0 else 0.0
        features['flag_fdc_qualitydegrade_high_180d'] = 1 if features['ratio_fdc_qualitydegrade_180d'] > 0.2 else 0

        # 9. 贷款重叠率 (30d/60d)
        for days, suffix in [(30, '30d'), (60, '60d')]:
            loans_w = filter_loans_window(days)
            if len(loans_w) < 2:
                features[f'ratio_fdc_loanoverlap_{suffix}'] = 0.0
                continue
            # 计算时间重叠天数
            total_overlap = 0
            total_days = 0
            for i in range(len(loans_w)):
                s1 = self._safe_parse_date(loans_w[i].get('tgl_penyaluran_dana', ''))
                e1 = self._safe_parse_date(loans_w[i].get('tgl_jatuh_tempo_pinjaman', '')) or s1 + timedelta(days=30)
                if not s1: continue
                total_days += (e1 - s1).days
                for j in range(i + 1, len(loans_w)):
                    s2 = self._safe_parse_date(loans_w[j].get('tgl_penyaluran_dana', ''))
                    e2 = self._safe_parse_date(loans_w[j].get('tgl_jatuh_tempo_pinjaman', '')) or s2 + timedelta(days=30)
                    if not s2: continue
                    overlap = max(0, min(e1, e2) - max(s1, s2)).days
                    total_overlap += overlap
            features[f'ratio_fdc_loanoverlap_{suffix}'] = total_overlap / total_days if total_days > 0 else 0.0
        features['flag_fdc_loanoverlap_high_30d'] = 1 if features['ratio_fdc_loanoverlap_30d'] > 0.5 else 0

        # 10. 债务覆盖率 (全量/90d)
        base = original_data.get('params', {}).get('base', {})
        salary = float(base.get('salary', 0))
        outstanding_all = sum(float(l.get('sisa_pinjaman_berjalan', 0)) for l in pinjaman if l.get('status_pinjaman') == 'O')
        features['ratio_fdc_debtcoverage_all'] = salary / outstanding_all if outstanding_all > 0 else 1.0
        loans_90 = filter_loans_window(90)
        outstanding_90 = sum(float(l.get('sisa_pinjaman_berjalan', 0)) for l in loans_90 if l.get('status_pinjaman') == 'O')
        features['ratio_fdc_debtcoverage_90d'] = salary / outstanding_90 if outstanding_90 > 0 else 1.0
        features['flag_fdc_debtcoverage_low_all'] = 1 if features['ratio_fdc_debtcoverage_all'] < 0.5 else 0

        # 11. 重组周期 (6m/12m)
        for days, suffix in [(180, '6m'), (360, '12m')]:
            loans_w = filter_loans_window(days)
            cycles = []
            for l in loans_w:
                if l.get('status_pinjaman') == 'O':
                    dis_dt = self._safe_parse_date(l.get('tgl_penyaluran_dana', ''))
                    restr_dt = self._safe_parse_date(l.get('tgl_restruktur', ''))
                    if dis_dt and restr_dt:
                        cycles.append((dis_dt - restr_dt).days)
            features[f'avg_fdc_restructcycle_{suffix}'] = sum(cycles) / len(cycles) if cycles else 0.0
        features['flag_fdc_restructcycle_short_6m'] = 1 if features['avg_fdc_restructcycle_6m'] < 60 else 0

        return features

    def _calc_base_features(self, data: Dict, apply_time_dt: datetime) -> Dict:
        features = {}
        base = data.get('params', {}).get('base', {})
        id_card = base.get('idCard', '')
        birthday_str = base.get('birthday', '')
        salary = float(base.get('salary', 0))
        job = str(base.get('job', ''))

        # 1. GAID聚类 (24h/6h) - 依赖历史base数据
        history_base = data.get('history_base', [])
        for hours, suffix in [(24, '24h'), (6, '6h')]:
            cutoff = apply_time_dt - timedelta(hours=hours)
            count = sum(1 for h in history_base if h.get('gaid') == base.get('gaid') and self._safe_parse_date(h.get('applyTime', ''), '%Y-%m-%d %H:%M:%S') and self._safe_parse_date(h.get('applyTime', ''), '%Y-%m-%d %H:%M:%S') >= cutoff)
            features[f'count_base_gaidcluster_{suffix}'] = count
        features['flag_base_gaidcluster_high_24h'] = 1 if features['count_base_gaidcluster_24h'] >= 5 else 0

        # 2. 身份证生日/年龄校验
        id_birth = None
        if len(id_card) >= 14:
            try:
                id_birth = datetime.strptime(id_card[6:14], '%Y%m%d')
            except:
                pass

        # 解析申请人生日
        base_birth = self._safe_parse_date(birthday_str, '%d-%m-%Y')

        # 生日不一致标记
        mismatch_bday = 0
        if id_birth and base_birth:
            mismatch_bday = 1 if id_birth.date() != base_birth.date() else 0
        features['flag_base_idcard_birthday_mismatch'] = mismatch_bday

        # 年龄越界标记
        age = 0
        if id_birth:
            age = apply_time_dt.year - id_birth.year - ((apply_time_dt.month, apply_time_dt.day) < (id_birth.month, id_birth.day))
        features['flag_base_idcard_age_mismatch'] = 1 if age < 18 or age > 65 else 0

        # 身份证不一致总数
        features['count_base_idcard_inconsistency_all'] = mismatch_bday + features['flag_base_idcard_age_mismatch']

        # 3. 收入差距 (30d/90d)
        pinjaman = data.get('params', {}).get('FDC', {}).get('pinjaman', [])
        for days, suffix in [(30, '30d'), (90, '90d')]:
            cutoff = apply_time_dt - timedelta(days=days)
            valid_loans = [l for l in pinjaman if l.get('status_pinjaman') in ['O', 'L'] and self._safe_parse_date(l.get('tgl_penyaluran_dana', '')) and self._safe_parse_date(l.get('tgl_penyaluran_dana', '')) >= cutoff]
            avg_income = sum(float(l.get('pendapatan', l.get('nilai_pendanaan', 0))) for l in valid_loans) / len(valid_loans) if valid_loans else 0
            features[f'ratio_base_fdcincomegap_{suffix}'] = abs(salary - avg_income) / salary if salary > 0 else 0.0
        features['flag_base_fdcincomegap_high_30d'] = 1 if features['ratio_base_fdcincomegap_30d'] > 0.5 and len([l for l in pinjaman if l.get('status_pinjaman') == 'O' and self._safe_parse_date(l.get('tgl_penyaluran_dana', '')) and self._safe_parse_date(l.get('tgl_penyaluran_dana', '')) >= apply_time_dt - timedelta(days=90)]) > 2 else 0

        # 4. 年龄职业风险
        risk_score = 0.8
        if 18 <= age <= 25 and job in ['1', '2']:
            risk_score = 1.5
        elif 26 <= age <= 35:
            risk_score = 1.0
        features['ratio_base_agejobrisk_all'] = risk_score
        features['flag_base_agejobrisk_high_all'] = 1 if 18 <= age <= 25 and job in ['1', '2'] else 0

        # 5. 年轻职业占比
        total_records = len(history_base) + 1 if history_base else 1
        young_job_count = sum(1 for h in history_base if 18 <= (apply_time_dt.year - self._safe_parse_date(h.get('idCard', '')[6:14], '%Y%m%d').year) <= 25 and str(h.get('job', '')) in ['1', '2', '3'])
        if 18 <= age <= 25 and job in ['1', '2', '3']:
            young_job_count += 1
        features['ratio_base_agejobrisk_young_all'] = young_job_count / total_records

        # 6. 收入波动 vs 贷款规模 (6m/12m)
        salary_hist = [float(h.get('salary', salary)) for h in history_base] + [salary]
        for months, suffix, days in [(6, '6m', 180), (12, '12m', 360)]:
            if len(salary_hist) < 2:
                features[f'ratio_base_incomevol_vs_loansize_{suffix}'] = 0.0
                continue
            mean_s = sum(salary_hist) / len(salary_hist)
            var_s = sum((x - mean_s) ** 2 for x in salary_hist) / len(salary_hist)
            std_s = math.sqrt(var_s)
            loans_w = [l for l in pinjaman if l.get('status_pinjaman') == 'O' and self._safe_parse_date(l.get('tgl_penyaluran_dana', '')) and self._safe_parse_date(l.get('tgl_penyaluran_dana', '')) >= apply_time_dt - timedelta(days=days)]
            avg_loan = sum(float(l.get('nilai_pendanaan', 0)) for l in loans_w) / len(loans_w) if loans_w else 0
            features[f'ratio_base_incomevol_vs_loansize_{suffix}'] = std_s / avg_loan if avg_loan > 0 else 0.0
        features['flag_base_incomevol_vs_loansize_high_12m'] = 1 if features['ratio_base_incomevol_vs_loansize_12m'] > 1.5 and (sum(float(l.get('nilai_pendanaan', 0)) for l in pinjaman if l.get('status_pinjaman') == 'O') / max(1, len([l for l in pinjaman if l.get('status_pinjaman') == 'O']))) > 5000000 else 0

        # 7. 渠道切换 (30d/90d)
        for days, suffix in [(30, '30d'), (90, '90d')]:
            cutoff = apply_time_dt - timedelta(days=days)
            channels = {h.get('channel') for h in history_base if self._safe_parse_date(h.get('applyTime', ''), '%Y-%m-%d %H:%M:%S') and self._safe_parse_date(h.get('applyTime', ''), '%Y-%m-%d %H:%M:%S') >= cutoff}
            if base.get('channel'):
                channels.add(base.get('channel'))
            features[f'count_base_channelswitch_{suffix}'] = len(channels)
        features['flag_base_channelswitch_high_30d'] = 1 if features['count_base_channelswitch_30d'] >= 3 else 0

        return features