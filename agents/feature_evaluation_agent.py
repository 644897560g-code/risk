"""
Feature Evaluation Agent - 特征评估Agent

职责：
1. 划分训练集和OOT（Out-of-Time）数据集
2. 计算每个特征的IV值（筛选 >= 0.02）
3. 计算PSI稳定性（筛选 <= 0.25）
4. 计算非缺失覆盖率（筛选 > 5%）
5. 输出HTML评估报告

输入：审核通过的特征代码 + 样本数据
输出：HTML报告 + 通过筛选的特征列表
"""

import json
import os
import sys
import datetime
import requests
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from utils.llm_client import LLMClient


class FeatureEvaluator:
    """特征评估Agent"""

    def __init__(self, ref_distributions: Dict = None):
        self.features_calculator = None
        self.sample_data = None
        self.train_data = None
        self.oot_data = None
        self.llm_client = LLMClient()
        self.evaluation_results = {}
        self.ref_distributions = ref_distributions or {}

    def load_feature_calculator(self, code_path: str):
        """加载特征计算器代码"""
        print(f"Loading feature calculator from: {code_path}")

        # 动态导入特征计算器模块
        import importlib.util
        spec = importlib.util.spec_from_file_location("features_calculator", code_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.features_calculator = module.FeatureCalculator(
            app_category_cache=self._load_app_cache(),
            ref_distributions=self.ref_distributions
        )
        print(f"   Loaded FeatureCalculator successfully (app_cache: {len(self._load_app_cache())} packages)")

    def _load_app_cache(self) -> Dict:
        """加载APP分类缓存"""
        cache_path = 'outputs/app_analysis/classification_complete_11850.json'
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                classes = data.get('classifications', data)
                if isinstance(classes, dict):
                    return classes
            except Exception as e:
                print(f"  ⚠️ 加载APP分类缓存失败: {e}")
        return {}

    def load_short_urls(self, short_url_file: str) -> List[str]:
        """加载短链URL文件"""
        print(f"Loading short URLs from: {short_url_file}")
        urls = []
        with open(short_url_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    urls.append(line)
        print(f"   Loaded {len(urls)} URLs")
        return urls

    def fetch_json_from_url(self, url: str, timeout: int = 30) -> Dict:
        """从URL获取JSON数据"""
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"    Warning: Failed to fetch {url}: {e}")
            return {}

    def load_labels_from_excel(self, excel_path: str) -> pd.DataFrame:
        """从Excel加载好坏标签"""
        print(f"Loading labels from Excel: {excel_path}")
        df = pd.read_excel(excel_path)
        print(f"   Loaded {len(df)} labels")

        # 确保有必要的列
        if 'source_order_no' in df.columns and 'is_overdue' in df.columns:
            return df[['source_order_no', 'is_overdue']]
        else:
            print(f"   Warning: Excel columns not as expected. Columns: {df.columns.tolist()}")
            return df

    def load_sample_data_local(self, short_url_file: str, labels_excel: str = None,
                                sample_size: int = None, data_dir: str = 'data/all_samples') -> int:
        """从本地文件加载样本数据（替代HTTP远程拉取）

        从短链文件获取订单ID，然后在本地 data_dir 目录查找对应的JSON文件加载。
        相比HTTP方式，速度更快且没有超时限制。

        Args:
            short_url_file: 短链文件路径（用于获取订单ID顺序）
            labels_excel: Excel标签文件路径
            sample_size: 采样数量（None=全部）
            data_dir: 本地样本数据目录

        Returns:
            成功加载的样本数量
        """
        import sys
        print(f"\n{'='*70}")
        print("加载本地样本数据")
        print(f"{'='*70}")
        sys.stdout.flush()

        # 1. 加载短链URL（只用来提取订单ID）
        print("  [load] loading short URLs...")
        sys.stdout.flush()
        urls = self.load_short_urls(short_url_file)
        print(f"  [load] loaded {len(urls)} URLs")

        # 2. 加载标签
        labels_df = None
        if labels_excel and os.path.exists(labels_excel):
            labels_df = self.load_labels_from_excel(labels_excel)
            # 构建订单号→标签的快速查找字典
            label_map = {}
            for _, row in labels_df.iterrows():
                order_id = str(row.get('source_order_no', '')).strip()
                label_val = int(row.get('is_overdue', -1))
                if order_id:
                    label_map[order_id] = label_val
            print(f"   标签查找表: {len(label_map)}个订单")
        else:
            label_map = {}

        # 3. 从本地文件加载
        print(f"   从 {data_dir} 加载样本文件...")
        samples = []
        matched_labels = 0

        for i, url in enumerate(urls):
            if sample_size and i >= sample_size:
                break

            if i % 500 == 0:
                print(f"   Progress: {i}/{len(urls)}")

            # 从URL提取订单ID
            order_id = url.split('/')[-1].strip()

            # 本地文件路径
            local_path = os.path.join(data_dir, f"{order_id}.json")
            if not os.path.exists(local_path):
                continue

            try:
                with open(local_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                continue

            # 确保orderId一致
            data_order_id = data.get('orderId', '')
            if data_order_id and data_order_id != order_id:
                order_id = data_order_id

            # 合并标签
            if label_map:
                lbl = label_map.get(order_id, label_map.get(data_order_id, -1))
                data['is_overdue'] = lbl
                if lbl >= 0:
                    matched_labels += 1
            else:
                data['is_overdue'] = -1

            samples.append(data)

        self.sample_data = samples
        print(f"\n   加载完成: {len(samples)}个样本 (匹配标签: {matched_labels})")
        return len(samples)

    def load_sample_data(self, short_url_file: str, labels_excel: str = None, sample_size: int = None):
        """加载样本数据（从短链和Excel标签）

        Args:
            short_url_file: 短链URL文件路径
            labels_excel: Excel标签文件路径（可选）
            sample_size: 采样数量（None=全部）
        """
        print(f"\n{'='*70}")
        print("加载样本数据")
        print(f"{'='*70}")

        # 1. 加载短链URL
        urls = self.load_short_urls(short_url_file)

        # 1b. 按URL文件名中的日期排序，提高标签匹配率
        def _sort_urls_by_date(url_list):
            import re

            def extract_date(url):
                # 从URL末尾提取 YYYYMMDD 格式的日期
                # URL格式示例: .../id002luzt2026030909514327 → 20260309
                filename = url.split('/')[-1]
                m = re.search(r'(\d{8})', filename)
                return m.group(1) if m else '99999999'
            return sorted(url_list, key=extract_date)

        urls = _sort_urls_by_date(urls)
        print(f"   URL按日期排序完成，前5个: {[url.split('/')[-1][:20] for url in urls[:5]]}")

        # 2. 加载标签（如果有）
        labels_df = None
        if labels_excel and os.path.exists(labels_excel):
            labels_df = self.load_labels_from_excel(labels_excel)

        # 3. 从URL获取JSON数据
        print(f"\n从 {len(urls)} 个URL获取JSON数据...")

        samples = []
        for i, url in enumerate(urls):
            if sample_size and i >= sample_size:
                break

            if i % 100 == 0:
                print(f"   Progress: {i}/{len(urls)}")

            data = self.fetch_json_from_url(url)
            if not data:
                continue

            # 提取订单号
            order_id = data.get('orderId', '')

            # 如果有标签，合并标签
            if labels_df is not None and order_id:
                label_row = labels_df[labels_df['source_order_no'] == order_id]
                if not label_row.empty:
                    data['is_overdue'] = int(label_row.iloc[0]['is_overdue'])
                else:
                    data['is_overdue'] = -1  # 未匹配
            else:
                data['is_overdue'] = -1  # 无标签

            samples.append(data)

        self.sample_data = samples
        print(f"\n   Loaded {len(samples)} samples with labels")

    def load_sample_data_legacy(self, data_path: str):
        """加载样本数据（旧方法，保留兼容）"""
        print(f"Loading sample data from: {data_path}")

        if data_path.endswith('.json'):
            # 单条JSON数据
            with open(data_path, 'r', encoding='utf-8') as f:
                self.sample_data = json.load(f)
            print(f"   Loaded single sample: {data_path}")
        elif data_path.endswith('.jsonl') or data_path.endswith('.txt'):
            # JSONL文件（多条JSON）
            samples = []
            with open(data_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        samples.append(json.loads(line))
            self.sample_data = samples
            print(f"   Loaded {len(samples)} samples from JSONL")
        elif data_path.endswith('.xlsx') or data_path.endswith('.xls'):
            # Excel文件
            import openpyxl
            df = pd.read_excel(data_path)
            self.sample_data = df
            print(f"   Loaded {len(df)} samples from Excel")
        else:
            raise ValueError(f"Unsupported data format: {data_path}")

    def split_data(self, oot_ratio: float = 0.2, time_column: str = None):
        """划分训练集和OOT数据集

        Args:
            oot_ratio: OOT数据集比例
            time_column: 时间列名（用于OOT划分）
        """
        print(f"\n{'='*70}")
        print("1. 数据集划分")
        print(f"{'='*70}")

        if isinstance(self.sample_data, list):
            # JSON数据列表
            if time_column:
                # 按时间排序，最新的作为OOT
                def extract_time(x):
                    if isinstance(x, dict):
                        return x.get(time_column, 0)
                    return 0

                sorted_data = sorted(self.sample_data, key=extract_time, reverse=True)
                oot_size = int(len(sorted_data) * oot_ratio)
                self.oot_data = sorted_data[:oot_size]
                self.train_data = sorted_data[oot_size:]
            else:
                # 随机划分
                np.random.seed(42)
                indices = np.random.permutation(len(self.sample_data))
                oot_size = int(len(self.sample_data) * oot_ratio)
                oot_indices = indices[:oot_size]
                train_indices = indices[oot_size:]
                self.oot_data = [self.sample_data[i] for i in oot_indices]
                self.train_data = [self.sample_data[i] for i in train_indices]

        elif isinstance(self.sample_data, pd.DataFrame):
            # DataFrame
            if time_column and time_column in self.sample_data.columns:
                sorted_df = self.sample_data.sort_values(time_column, ascending=False)
                oot_size = int(len(sorted_df) * oot_ratio)
                self.oot_data = sorted_df.iloc[:oot_size]
                self.train_data = sorted_df.iloc[oot_size:]
            else:
                from sklearn.model_selection import train_test_split
                self.train_data, self.oot_data = train_test_split(
                    self.sample_data, test_size=oot_ratio, random_state=42
                )

        print(f"   Train set size: {len(self.train_data)}")
        print(f"   OOT set size: {len(self.oot_data)}")
        print(f"   OOT ratio: {oot_ratio:.1%}")

    def compute_reference_distributions(self) -> Dict:
        """从训练数据预计算T010-T012所需的参考分布

        需要在 split_data() 之后调用。

        Returns:
            参考分布字典
        """
        print("\nPass 1: Computing reference distributions for T010-T012...")
        try:
            from agents.feature_mass_producer import precompute_references
            refs = precompute_references(self.train_data)
            self.ref_distributions = refs
            print(f"   Salary dist: {len(refs.get('salary_distribution', []))} samples")
            print(f"   Loan amt dist: {len(refs.get('loan_amount_distribution', []))} samples")
            print(f"   Inquiry dist: {len(refs.get('inquiry_count_distribution', []))} samples")
            print(f"   Applist dist: {len(refs.get('applist_count_distribution', []))} samples")
            return refs
        except ImportError as e:
            print(f"   Warning: feature_mass_producer not available ({e}), skipping ref distributions")
            return {}
        except Exception as e:
            print(f"   Warning: ref distribution computation failed: {e}")
            return {}

    def calculate_features_on_dataset(self, dataset: List[Dict]) -> pd.DataFrame:
        """在数据集上计算特征

        Args:
            dataset: 样本数据列表

        Returns:
            DataFrame with features
        """
        import sys
        total = len(dataset)
        print(f"  Calculating features on {total} samples...")
        sys.stdout.flush()

        features_list = []
        for i, sample in enumerate(dataset):
            if (i + 1) % 100 == 0 or i == 0:
                print(f"    Feature calc progress: {i+1}/{total} samples...")
                sys.stdout.flush()
            try:
                # 计算特征
                features = self.features_calculator.calculate_all(sample)
                features['sample_index'] = i

                # 提取目标变量（好坏标签）
                if isinstance(sample, dict):
                    features['target'] = sample.get('is_overdue', -1)

                features_list.append(features)
            except Exception as e:
                print(f"    Warning: Failed to calculate features for sample {i}: {e}")
                continue

        if not features_list:
            return pd.DataFrame()

        df_features = pd.DataFrame(features_list)
        print(f"   Calculated {len(df_features.columns)} features for {len(df_features)} samples")
        return df_features

    def calculate_iv(self, df_train: pd.DataFrame, feature_name: str, target_col: str = 'target') -> float:
        """计算特征的IV值（Information Value）

        Args:
            df_train: 训练数据
            feature_name: 特征名称
            target_col: 目标变量列名

        Returns:
            IV value
        """
        if feature_name not in df_train.columns:
            return 0.0

        df = df_train[[feature_name, target_col]].dropna()
        if len(df) == 0:
            return 0.0

        # 过滤掉未匹配标签的样本（target=-1）
        df = df[df[target_col] >= 0]
        if len(df) == 0:
            return 0.0

        # 对于连续特征，分箱处理
        values = df[feature_name]
        target = df[target_col]

        # 如果特征值过多，进行分箱
        if len(values.unique()) > 20:
            # 等频分箱，分为10箱
            n_bins = 10
            df_temp = df.copy()
            df_temp['bin'] = pd.qcut(values, q=n_bins, duplicates='drop')
            bin_table = df_temp.groupby('bin')[target_col].agg(['sum', 'count'])
        else:
            bin_table = df.groupby(feature_name)[target_col].agg(['sum', 'count'])

        # 计算好坏比例
        total_good = (target == 0).sum()
        total_bad = (target == 1).sum()

        if total_good == 0 or total_bad == 0:
            return 0.0

        iv = 0.0
        for _, row in bin_table.iterrows():
            good_pct = (row['count'] - row['sum']) / total_good if total_good > 0 else 0
            bad_pct = row['sum'] / total_bad if total_bad > 0 else 0

            if good_pct > 0 and bad_pct > 0:
                iv += (bad_pct - good_pct) * np.log(bad_pct / good_pct)

        return iv

    def calculate_psi(self, df_train: pd.DataFrame, df_oot: pd.DataFrame, feature_name: str) -> float:
        """计算特征的PSI（Population Stability Index）

        Args:
            df_train: 训练数据
            df_oot: OOT数据
            feature_name: 特征名称

        Returns:
            PSI value
        """
        if feature_name not in df_train.columns or feature_name not in df_oot.columns:
            return 0.0

        train_values = df_train[feature_name].dropna()
        oot_values = df_oot[feature_name].dropna()

        if len(train_values) == 0 or len(oot_values) == 0:
            return 0.0

        # 对于连续特征，分箱处理
        if len(train_values.unique()) > 20:
            # 使用训练集的分位数进行分箱
            n_bins = 10
            bins = pd.qcut(train_values, q=n_bins, duplicates='drop', retbins=True)[1]

            # 对两个数据集应用相同的分箱
            train_binned = pd.cut(train_values, bins=bins, include_lowest=True)
            oot_binned = pd.cut(oot_values, bins=bins, include_lowest=True)

            train_dist = train_binned.value_counts(normalize=True)
            oot_dist = oot_binned.value_counts(normalize=True)
        else:
            train_dist = train_values.value_counts(normalize=True)
            oot_dist = oot_values.value_counts(normalize=True)

        # 对齐索引
        all_bins = sorted(set(train_dist.index) | set(oot_dist.index))
        psi = 0.0

        for bin_val in all_bins:
            train_pct = train_dist.get(bin_val, 0.001)  # 避免除零
            oot_pct = oot_dist.get(bin_val, 0.001)

            psi += (oot_pct - train_pct) * np.log(oot_pct / train_pct)

        return psi

    def calculate_coverage(self, df_train: pd.DataFrame, feature_name: str) -> float:
        """计算特征的非缺失覆盖率

        Args:
            df_train: 训练数据
            feature_name: 特征名称

        Returns:
            Coverage rate (0-1)
        """
        if feature_name not in df_train.columns:
            return 0.0

        non_null_count = df_train[feature_name].notna().sum()
        total_count = len(df_train)

        return non_null_count / total_count if total_count > 0 else 0.0

    def evaluate_all_features(self, iv_threshold: float = 0.02, psi_threshold: float = 0.25,
                               coverage_threshold: float = 0.05):
        """评估所有特征

        Args:
            iv_threshold: IV阈值（>= 通过）
            psi_threshold: PSI阈值（<= 通过）
            coverage_threshold: 覆盖率阈值（> 通过）
        """
        print(f"\n{'='*70}")
        print("2. 特征评估")
        print(f"{'='*70}")

        # 在训练集和OOT集上计算特征
        df_train = self.calculate_features_on_dataset(self.train_data)
        df_oot = self.calculate_features_on_dataset(self.oot_data)

        # 统计有效标签样本量
        matched_train = (df_train['target'] >= 0).sum() if 'target' in df_train.columns else 0
        matched_oot = (df_oot['target'] >= 0).sum() if 'target' in df_oot.columns else 0
        print(f"   Matched labels: train={matched_train}, oot={matched_oot}")

        if df_train.empty:
            print("   ⚠️  训练集特征计算失败")
            return

        feature_names = [col for col in df_train.columns if col not in ['sample_index', 'target']]
        print(f"\n   评估 {len(feature_names)} 个特征\n")

        results = []
        for feature_name in feature_names:
            # 计算指标
            iv = self.calculate_iv(df_train, feature_name)
            psi = self.calculate_psi(df_train, df_oot, feature_name)
            coverage = self.calculate_coverage(df_train, feature_name)

            # 判断是否通过
            passed = (iv >= iv_threshold) and (psi <= psi_threshold) and (coverage > coverage_threshold)

            # 清理 NaN 值（JSON 无法序列化 NaN）
            import math
            if math.isnan(iv):
                iv = 0.0
            if math.isnan(psi):
                psi = 0.0
            if math.isnan(coverage):
                coverage = 0.0

            results.append({
                'feature_name': feature_name,
                'iv': iv,
                'psi': psi,
                'coverage': coverage,
                'passed': passed
            })

            # 打印进度
            status = "✅" if passed else "❌"
            print(f"   {status} {feature_name:50s} IV={iv:.4f}  PSI={psi:.4f}  Cov={coverage:.2%}")

        self.evaluation_results = {
            'results': results,
            'total_features': len(feature_names),
            'passed_features': len([r for r in results if r['passed']]),
            'thresholds': {
                'iv': iv_threshold,
                'psi': psi_threshold,
                'coverage': coverage_threshold
            }
        }

        print(f"\n   通过: {self.evaluation_results['passed_features']}/{len(feature_names)}")

    def generate_html_report(self, output_path: str = 'outputs/evaluation/feature_evaluation_report.html'):
        """生成HTML评估报告"""
        print(f"\n{'='*70}")
        print("3. 生成HTML报告")
        print(f"{'='*70}")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        if not self.evaluation_results:
            print("   ⚠️  没有评估结果可报告")
            return

        # 生成HTML
        html_content = self._build_html_report()

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"   Report saved: {output_path}")

    @staticmethod
    def _simple_desc(feature_name: str) -> str:
        """为HTML报告生成简短的中文特征描述"""
        name = feature_name

        # ---- T016 d_ 衍生特征 ----
        if name.startswith("d_"):
            rest = name[2:]
            parts = rest.split("_")
            d_type = parts[0] if parts else ""
            d_rest = "_".join(parts[1:]) if len(parts) > 1 else ""

            _domain_map = {
                "highrisk": "高风险", "loan": "借贷", "banking": "银行",
                "ewallet": "电子钱包", "gambling": "赌博", "shopping": "购物",
                "consume": "消费", "amt": "金额", "bal": "在贷余额",
                "inc": "收入", "dpd30": "DPD30逾期", "aktif": "活跃平台",
                "highrisk_loan": "高风险借贷", "fdcpin": "FDC贷款",
                "app": "安装APP", "uniq": "唯一值",
            }
            _time_map = {
                "30d": "近30天", "60d": "近60天", "90d": "近90天",
                "180d": "近180天", "7d": "近7天", "15d": "近15天",
                "7v90d": "7天vs90天", "3d": "近3天",
            }

            def _inner_desc(n: str) -> str:
                """简短内部描述"""
                for k, v in sorted(_time_map.items(), key=lambda x: -len(x[0])):
                    if n.endswith("_" + k):
                        base = n[:-(len(k)+1)]
                        for dk, dv in sorted(_domain_map.items(), key=lambda x: -len(x[0])):
                            if dk in base:
                                return dv
                        return base
                for dk, dv in sorted(_domain_map.items(), key=lambda x: -len(x[0])):
                    if dk in n:
                        return dv
                return n

            # Extract time window from d_rest
            time_str = ""
            for tk, tv in sorted(_time_map.items(), key=lambda x: -len(x[0])):
                if d_rest.endswith("_" + tk) or d_rest.endswith(tk):
                    time_str = tv
                    if d_rest.endswith("_" + tk):
                        base_rest = d_rest[:-(len(tk)+1)]
                    else:
                        base_rest = d_rest[:-(len(tk))]
                    break
            else:
                base_rest = d_rest

            type_labels = {
                "dens": "密度", "ratio": "比值", "wcomb": "加权组合",
                "vel": "速度变化", "sq": "平方值", "log": "对数值",
                "diff": "差值", "high": "高值标记",
            }
            type_label = type_labels.get(d_type, d_type)

            decay_suffix = ""
            if d_type == "log":
                for suf in ["_r005", "_r01", "_r02"]:
                    if base_rest.endswith(suf):
                        decay_suffix = suf
                        base_rest = base_rest[:-len(suf)]
                        break

            inner = _inner_desc(base_rest)
            if time_str:
                return f"{time_str} {inner}的{type_label}{decay_suffix}"
            return f"{inner}的{type_label}{decay_suffix}"

        # ---- Common patterns ----
        agg_prefixes = ["cnt_", "count_", "max_", "avg_", "sum_", "min_", "prop_", "perc_", "conc_", "ovlap_", "da_", "uniq_"]
        time_suffixes = ["_30d", "_60d", "_90d", "_180d", "_7d", "_15d", "_3d", "_7v90d", "_30v180d"]

        agg_map = {
            "cnt": "数量", "count": "数量", "max": "最大值", "avg": "均值",
            "sum": "总和", "min": "最小值", "prop": "比例", "perc": "百分比",
            "conc": "集中度", "ovlap": "重叠度", "da": "数据分析", "uniq": "唯一值",
        }

        stripped = name
        agg_label = ""
        for prefix in agg_prefixes:
            if stripped.startswith(prefix):
                agg_label = agg_map.get(prefix.rstrip("_"), prefix.rstrip("_"))
                stripped = stripped[len(prefix):]
                break

        time_label = ""
        for suffix in time_suffixes:
            if stripped.endswith(suffix):
                time_label = suffix.lstrip("_")
                stripped = stripped[:-len(suffix)]
                break

        if agg_label:
            parts = [agg_label]
            if stripped:
                parts.append(stripped)
            if time_label:
                parts.append(f"({time_label})")
            return " ".join(parts)

        return name

    def _build_html_report(self) -> str:
        """构建HTML报告内容"""
        results = self.evaluation_results['results']
        thresholds = self.evaluation_results['thresholds']

        # 排序：按IV降序
        results_sorted = sorted(results, key=lambda x: x['iv'], reverse=True)

        html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>特征评估报告</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }
        h2 { color: #555; margin-top: 30px; }
        .summary { background: white; padding: 20px; border-radius: 8px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }
        .metric-card { background: #f9f9f9; padding: 15px; border-radius: 6px; text-align: center; }
        .metric-value { font-size: 2em; font-weight: bold; color: #4CAF50; }
        .metric-label { color: #666; font-size: 0.9em; margin-top: 5px; }
        table { width: 100%; border-collapse: collapse; background: white; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        th { background: #4CAF50; color: white; padding: 12px; text-align: left; white-space: nowrap; }
        .desc-cell { color: #555; font-size: 0.9em; max-width: 250px; }
        td { padding: 10px 12px; border-bottom: 1px solid #ddd; }
        tr:hover { background: #f5f5f5; }
        .pass { color: #4CAF50; font-weight: bold; }
        .fail { color: #f44336; font-weight: bold; }
        .threshold-info { background: #e3f2fd; padding: 15px; border-radius: 6px; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>特征评估报告</h1>
        <p style="color: #666;">生成时间: """ + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</p>

        <div class="summary">
            <h2>概要</h2>
            <div class="summary-grid">
                <div class="metric-card">
                    <div class="metric-value">""" + str(self.evaluation_results['total_features']) + """</div>
                    <div class="metric-label">总特征数</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value" style="color: """ + ('#4CAF50' if self.evaluation_results['passed_features'] > 0 else '#f44336') + """;">
""" + str(self.evaluation_results['passed_features']) + """</div>
                    <div class="metric-label">通过筛选</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">""" + f"{self.evaluation_results['passed_features']/max(self.evaluation_results['total_features'],1)*100:.1f}%" + """</div>
                    <div class="metric-label">通过率</div>
                </div>
            </div>
        </div>

        <div class="threshold-info">
            <h3>筛选阈值</h3>
            <ul>
                <li>IV >= """ + f"{thresholds['iv']}" + """</li>
                <li>PSI <= """ + f"{thresholds['psi']}" + """</li>
                <li>覆盖率 > """ + f"{thresholds['coverage']*100:.1f}%" + """</li>
            </ul>
        </div>

        <h2>特征评估结果</h2>
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>特征名称</th>
                    <th>特征描述</th>
                    <th>IV</th>
                    <th>PSI</th>
                    <th>覆盖率</th>
                    <th>状态</th>
                </tr>
            </thead>
            <tbody>
"""

        for i, result in enumerate(results_sorted, 1):
            status_class = "pass" if result['passed'] else "fail"
            status_text = "✅ 通过" if result['passed'] else "❌ 未通过"
            desc = self._simple_desc(result['feature_name'])

            html += f"""                <tr>
                    <td>{i}</td>
                    <td><code>{result['feature_name']}</code></td>
                    <td class="desc-cell">{desc}</td>
                    <td>{result['iv']:.4f}</td>
                    <td>{result['psi']:.4f}</td>
                    <td>{result['coverage']:.2%}</td>
                    <td class="{status_class}">{status_text}</td>
                </tr>
"""

        html += """            </tbody>
        </table>
    </div>
</body>
</html>
"""

        return html

    def save_results(self, output_path: str = 'outputs/evaluation/passed_features.json'):
        """保存通过筛选的特征列表"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        passed = [r for r in self.evaluation_results.get('results', []) if r['passed']]

        # 清洗数据：将NaN/Inf转为None，bool转为int(0/1)
        import numpy as np

        def clean_val(v):
            if isinstance(v, float) or (isinstance(v, np.floating)):
                if v != v or v == float('inf') or v == float('-inf') or v == np.inf or v == -np.inf:
                    return None
            if isinstance(v, bool) or isinstance(v, np.bool_):
                return int(v)
            return v

        def clean_result(r):
            return {k: clean_val(v) for k, v in r.items()}

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({
                'passed_features': [clean_result(r) for r in passed],
                'total_passed': len(passed),
                'thresholds': self.evaluation_results.get('thresholds', {})
            }, f, ensure_ascii=False, indent=2)

        print(f"   Passed features saved: {output_path}")

    def run(self, code_path: str, short_url_file: str = None, labels_excel: str = None,
            sample_size: int = None, oot_ratio: float = 0.2, data_path: str = None,
            use_local: bool = False, data_dir: str = 'data/all_samples'):
        """主执行流程

        Args:
            code_path: 特征代码路径
            short_url_file: 短链URL文件路径
            labels_excel: Excel标签文件路径
            sample_size: 采样数量
            oot_ratio: OOT比例
            data_path: 旧版数据路径（兼容用）
        """
        print("=" * 70)
        print("特征评估Agent - 开始执行")
        print("=" * 70)

        # 1. 加载特征计算器
        self.load_feature_calculator(code_path)

        # 2. 加载样本数据
        if use_local:
            # 本地文件加载（更快、无超时、可加载全部2105个样本）
            count = self.load_sample_data_local(
                short_url_file=short_url_file,
                labels_excel=labels_excel,
                sample_size=sample_size,
                data_dir=data_dir
            )
            if count == 0:
                print("❌ 本地样本加载失败（无匹配文件），回退HTTP加载")
                self.load_sample_data(
                    short_url_file=short_url_file,
                    labels_excel=labels_excel,
                    sample_size=sample_size
                )
        elif short_url_file and os.path.exists(short_url_file):
            self.load_sample_data(
                short_url_file=short_url_file,
                labels_excel=labels_excel,
                sample_size=sample_size
            )
        elif data_path:
            # 兼容旧方式
            print(f"⚠️  使用旧版数据加载方式: {data_path}")
            self.load_sample_data_legacy(data_path)
        else:
            print("❌ 未指定有效数据源")
            return False

        # 3. 划分数据集
        self.split_data(oot_ratio=oot_ratio)

        # 4. 评估所有特征
        self.evaluate_all_features()

        # 5. 生成报告
        report_path = 'outputs/evaluation/feature_evaluation_report.html'
        self.generate_html_report(report_path)

        # 6. 保存结果
        results_path = 'outputs/evaluation/passed_features.json'
        self.save_results(results_path)

        print("\n" + "=" * 70)
        print("特征评估Agent - 执行完成")
        print("=" * 70)

        passed = self.evaluation_results.get('passed_features', 0)
        total = self.evaluation_results.get('total_features', 0)
        print(f"\n✅ 通过: {passed}/{total}")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Feature Evaluation Agent')
    parser.add_argument('--code-path', type=str, default=None, help='Path to feature calculator code')
    parser.add_argument('--short-urls', type=str, default='0421全样本短链.txt', help='Path to short URLs file')
    parser.add_argument('--labels', type=str, default='印尼模型分_2026_04_21_建模样本aiagent.xlsx', help='Path to labels Excel file')
    parser.add_argument('--sample-size', type=int, default=None, help='Number of samples to evaluate (None=all)')
    parser.add_argument('--oot-ratio', type=float, default=0.2, help='OOT split ratio')

    args = parser.parse_args()

    evaluator = FeatureEvaluator()

    # 从数据流注册表获取特征代码路径
    registry_file = 'outputs/feature_code/data_flow_registry.json'
    if os.path.exists(registry_file):
        with open(registry_file, 'r', encoding='utf-8') as f:
            registry = json.load(f)
        code_path = args.code_path if args.code_path else registry.get('latest_outputs', {}).get('features_calculator',
                       'outputs/feature_code/features_calculator_v2.py')
    else:
        code_path = args.code_path if args.code_path else 'outputs/feature_code/features_calculator_v2.py'

    # 使用真实数据运行
    evaluator.run(
        code_path=code_path,
        short_url_file=args.short_urls,
        labels_excel=args.labels,
        sample_size=args.sample_size,
        oot_ratio=args.oot_ratio
    )
