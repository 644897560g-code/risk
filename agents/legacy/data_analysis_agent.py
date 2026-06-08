"""
数据分析Agent
分析客户申请信息（base信息、applist、FDC数据）和贷后好坏表现，形成业务专有领域知识

核心逻辑：
1. 从短链加载样本JSON数据
2. 关联好坏标签
3. 统计各维度数据分布
4. 调用qwen3.6-plus进行深度分析
5. 输出结构化业务知识库JSON
"""

import os
import sys
import json
import logging
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.legacy.base_agent import BaseAgent
from data.data_loader import DataLoader, ShortLinkFetcher
from utils.json_utils import custom_json_dumps

logger = logging.getLogger(__name__)


class DataAnalysisAgent(BaseAgent):
    """数据分析Agent - 调用qwen3.6-plus分析印尼现金贷数据"""

    def __init__(self):
        super().__init__('data_analysis')
        self.data_loader = DataLoader()
        self.short_link_fetcher = ShortLinkFetcher()

    def load_and_prepare_data(self, short_links: List[str],
                                model_samples: pd.DataFrame,
                                sample_size: int = 100) -> Dict:
        """
        加载并准备分析数据

        Args:
            short_links: 短链URL列表
            model_samples: 建模样本DataFrame
            sample_size: 采样数量（避免过多API调用）

        Returns:
            准备好的数据字典
        """
        logger.info(f"从 {len(short_links)} 条短链中加载样本数据...")

        # 采样 - 只选取部分样本用于分析（控制API成本）
        sample_links = short_links[:sample_size]

        # 批量获取JSON数据
        json_data_list = self.short_link_fetcher.fetch_batch(sample_links)
        logger.info(f"成功获取 {len(json_data_list)} 条样本JSON数据")

        # 提取标签
        labels_df = model_samples[['source_order_no', 'is_overdue']].copy()
        labels_df.rename(columns={'source_order_no': 'orderId'}, inplace=True)

        # 构建统计数据
        stats = {
            'total_samples': len(model_samples),
            'overdue_count': int(model_samples['is_overdue'].sum()),
            'overdue_rate': round(float(model_samples['is_overdue'].mean()), 4),
            'source_distribution': model_samples['source'].value_counts().to_dict()
        }

        # 构建样本摘要（用于LLM分析）
        sample_summary = self._build_sample_summary(json_data_list, labels_df)

        return {
            'stats': stats,
            'json_data_list': json_data_list,
            'sample_summary': sample_summary,
            'labels_df': labels_df
        }

    def _build_sample_summary(self, json_data_list: List[Dict],
                                labels_df: pd.DataFrame) -> Dict:
        """
        构建样本数据摘要（供LLM分析）

        Args:
            json_data_list: JSON数据列表
            labels_df: 标签DataFrame

        Returns:
            样本摘要字典
        """
        # ⚠️ 关键修复：构建 orderId -> is_overdue 映射
        label_map = labels_df.set_index('orderId')['is_overdue'].to_dict()
        logger.info(f"构建标签映射: {len(label_map)} 个订单ID")

        summary = {
            'base_stats': self._summarize_base_with_overdue(json_data_list, label_map),
            'app_stats': self._summarize_apps(json_data_list),
            'fdc_stats': self._summarize_fdc(json_data_list)
        }

        return summary

    def _summarize_base_with_overdue(self, json_data_list: List[Dict], label_map: Dict) -> Dict:
        """基础信息统计 + 各维度逾期率分析"""
        # 分性别统计
        gender_stats = {'male': {'total': 0, 'overdue': 0}, 'female': {'total': 0, 'overdue': 0}}

        # 分年龄段统计（分箱）
        age_bins = [(0, 25), (26, 30), (31, 35), (36, 40), (41, 50), (51, 100)]
        age_bin_labels = ['18-25', '26-30', '31-35', '36-40', '41-50', '51+']
        age_stats = {label: {'total': 0, 'overdue': 0} for label in age_bin_labels}

        # 分职业统计
        job_stats = {}

        # 收入相关性
        salary_list = []
        is_overdue_list = []

        # 婚姻状况
        marriage_stats = {}

        # 子女情况
        children_stats = {}

        # 工作年限
        work_years_list = []

        for data in json_data_list:
            base = data.get('params', {}).get('base', {})
            order_id = data.get('orderId', '')
            is_overdue = label_map.get(order_id, 0)

            # 性别
            gender = base.get('gender')
            if gender is not None:
                if gender == 0:
                    gender_stats['male']['total'] += 1
                    if is_overdue:
                        gender_stats['male']['overdue'] += 1
                elif gender == 1:
                    gender_stats['female']['total'] += 1
                    if is_overdue:
                        gender_stats['female']['overdue'] += 1

            # 年龄
            birthday = base.get('birthday')
            if birthday:
                age = self._calc_age(birthday)
                for i, (low, high) in enumerate(age_bins):
                    if low <= age <= high:
                        age_stats[age_bin_labels[i]]['total'] += 1
                        if is_overdue:
                            age_stats[age_bin_labels[i]]['overdue'] += 1
                        break

            # 职业
            job = base.get('job')
            if job:
                job_str = str(job)
                if job_str not in job_stats:
                    job_stats[job_str] = {'total': 0, 'overdue': 0}
                job_stats[job_str]['total'] += 1
                if is_overdue:
                    job_stats[job_str]['overdue'] += 1

            # 收入
            salary = base.get('salary')
            if salary:
                salary_list.append(salary)
                is_overdue_list.append(is_overdue)

            # 婚姻
            marita = base.get('marita')
            if marita is not None:
                marita_str = str(marita)
                if marita_str not in marriage_stats:
                    marriage_stats[marita_str] = {'total': 0, 'overdue': 0}
                marriage_stats[marita_str]['total'] += 1
                if is_overdue:
                    marriage_stats[marita_str]['overdue'] += 1

            # 子女
            children = base.get('children')
            if children is not None:
                children_str = str(children)
                if children_str not in children_stats:
                    children_stats[children_str] = {'total': 0, 'overdue': 0}
                children_stats[children_str]['total'] += 1
                if is_overdue:
                    children_stats[children_str]['overdue'] += 1

            # 工作年限
            workYears = base.get('workYears')
            if workYears is not None:
                work_years_list.append(workYears)

        # 计算性别逾期率
        male_overdue_rate = (
            gender_stats['male']['overdue'] / gender_stats['male']['total']
            if gender_stats['male']['total'] > 0 else 0
        )
        female_overdue_rate = (
            gender_stats['female']['overdue'] / gender_stats['female']['total']
            if gender_stats['female']['total'] > 0 else 0
        )

        # 计算年龄分箱逾期率
        age_risk_bins = []
        for label in age_bin_labels:
            total = age_stats[label]['total']
            overdue = age_stats[label]['overdue']
            rate = overdue / total if total > 0 else 0
            if total > 0:  # 只有该年龄段有样本才返回
                age_risk_bins.append({
                    'bin': label,
                    'total_samples': total,
                    'overdue_count': overdue,
                    'overdue_rate': round(rate, 4)
                })

        # 计算职业逾期率（取top 10）
        job_risk_distribution = {}
        for job_code, stats in sorted(job_stats.items(), key=lambda x: x[1]['total'], reverse=True)[:10]:
            rate = stats['overdue'] / stats['total'] if stats['total'] > 0 else 0
            job_risk_distribution[job_code] = round(rate, 4)

        # 计算婚姻状况逾期率
        marriage_risk = {}
        for marita, stats in marriage_stats.items():
            rate = stats['overdue'] / stats['total'] if stats['total'] > 0 else 0
            marriage_risk[marita] = round(rate, 4)

        # 计算子女情况逾期率
        children_risk = {}
        for child, stats in children_stats.items():
            rate = stats['overdue'] / stats['total'] if stats['total'] > 0 else 0
            children_risk[child] = round(rate, 4)

        # 计算收入与逾期的相关性
        income_risk_correlation = 0.0
        if len(salary_list) > 2:
            correlation = np.corrcoef(salary_list, is_overdue_list)[0, 1]
            income_risk_correlation = round(float(correlation), 4)

        # 工作年限相关性
        work_years_risk_correlation = 0.0

        return {
            'gender_risk': {
                'male_overdue_rate': round(male_overdue_rate, 4),
                'female_overdue_rate': round(female_overdue_rate, 4),
                'total_samples': gender_stats['male']['total'] + gender_stats['female']['total'],
                'risk_ratio': round(male_overdue_rate / female_overdue_rate if female_overdue_rate > 0 else 0, 4)
            },
            'age_risk_bins': age_risk_bins,
            'income_risk_correlation': income_risk_correlation,
            'job_risk_distribution': job_risk_distribution,
            'marriage_risk': marriage_risk,
            'children_risk': children_risk,
            'work_years_risk_correlation': work_years_risk_correlation,
            'salary_stats': {
                'mean': float(np.mean(salary_list)) if salary_list else 0,
                'median': float(np.median(salary_list)) if salary_list else 0,
                'min': int(min(salary_list)) if salary_list else 0,
                'max': int(max(salary_list)) if salary_list else 0
            }
        }

    def _summarize_apps_with_llm_classification(self, json_data_list: List[Dict]) -> Dict:
        """应用列表统计 - 使用LLM科学分类结果（基于全量2916样本）"""
        app_counts = []
        all_packages = []

        # 加载LLM分类结果
        classification_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'outputs/app_analysis/app_classification_result.json'
        )

        llm_classifications = {}
        try:
            if os.path.exists(classification_path):
                with open(classification_path, 'r', encoding='utf-8') as f:
                    classification_data = json.load(f)
                    llm_classifications = classification_data.get('classifications', {})
                logger.info(f"已加载LLM分类结果: {len(llm_classifications)} 个应用")
            else:
                logger.warning(f"LLM分类文件不存在: {classification_path}，回退到关键词匹配")
                return self._summarize_apps_fallback(json_data_list)
        except Exception as e:
            logger.warning(f"加载LLM分类失败: {e}，回退到关键词匹配")
            return self._summarize_apps_fallback(json_data_list)

        for data in json_data_list:
            app_list = data.get('params', {}).get('appList', [])
            app_counts.append(len(app_list))

            for app in app_list:
                package = app.get('packageX', '')
                if not package:
                    continue

                all_packages.append(package)

        # 统计高频应用（Top 50）
        package_counts = pd.Series(all_packages).value_counts().head(50)

        # 基于LLM分类结果标记高风险应用
        high_risk_apps = {}
        risk_category_counts = {}

        # 定义高风险类别
        high_risk_categories = ['gambling', 'fintech_lending', 'cash_loan', 'installment']

        for package, freq in package_counts.items():
            if package in llm_classifications:
                category = llm_classifications[package].get('category', '')
                confidence = llm_classifications[package].get('confidence', '')

                if category in high_risk_categories and confidence in ['high', 'medium']:
                    high_risk_apps[package] = {
                        'risk_categories': [category],
                        'installation_count': freq,
                        'llm_confidence': confidence,
                        'llm_reason': llm_classifications[package].get('reason', '')
                    }

                    # 统计风险类型分布
                    risk_category_counts[category] = risk_category_counts.get(category, 0) + 1

        # 提取高频高风险应用（Top 20）
        sorted_high_risk = sorted(
            high_risk_apps.items(),
            key=lambda x: x[1]['installation_count'],
            reverse=True
        )
        top_high_risk = sorted_high_risk[:20]

        return {
            'app_count_stats': {
                'mean': float(np.mean(app_counts)),
                'median': float(np.median(app_counts)),
                'min': int(min(app_counts)) if app_counts else 0,
                'max': int(max(app_counts)) if app_counts else 0
            },
            'top_packages': package_counts.to_dict(),
            'high_risk_apps': {
                package: {
                    'risk_categories': info['risk_categories'],
                    'installation_count': info['installation_count'],
                    'llm_confidence': info.get('llm_confidence', ''),
                    'llm_reason': info.get('llm_reason', '')
                } for package, info in top_high_risk
            },
            'high_risk_app_types': list(risk_category_counts.keys()),
            'high_risk_app_type_distribution': risk_category_counts,
            'total_high_risk_apps': len(high_risk_apps),
            'high_risk_app_ratio': len(high_risk_apps) / len(set(all_packages)) if all_packages else 0,
            'classification_method': 'LLM_SCIENCE_CLASSIFICATION',
            'llm_classification_summary': {
                'total_classified_apps': len(llm_classifications),
                'high_risk_categories': high_risk_categories
            }
        }

    def _summarize_apps_fallback(self, json_data_list: List[Dict]) -> Dict:
        """应用列表统计 - 关键词匹配回退方案（当LLM分类不可用时）"""
        app_counts = []
        all_packages = []
        # 详细的高风险应用关键词
        high_risk_keywords = {
            'loan': ['loan', 'loans', 'pinjaman', 'kredit', 'kta', 'cashloan'],
            'cash': ['cash', 'dana', 'rupiah', 'uang', 'tunai'],
            'installment': ['installment', 'cicilan', 'paylater', 'paylater'],
            'fintech': ['fintek', 'fintech', 'finance', 'financial'],
            'overdue': ['telat', 'kolektabilitas', 'overdue', 'macet'],
            'multi_platform': ['kredivo', 'kredivo', 'finaccel', 'homecred', 'adaemi']
        }

        # 每个应用的出现频次
        package_freq = {}
        # 高风险应用标记
        high_risk_apps = {}

        for data in json_data_list:
            app_list = data.get('params', {}).get('appList', [])
            app_counts.append(len(app_list))

            for app in app_list:
                package = app.get('packageX', '')
                if not package:
                    continue

                all_packages.append(package)

                # 统计频次
                package_freq[package] = package_freq.get(package, 0) + 1

                # 检查是否为高风险应用
                risk_categories = []
                package_lower = package.lower()

                for category, keywords in high_risk_keywords.items():
                    if any(kw in package_lower for kw in keywords):
                        risk_categories.append(category)

                if risk_categories:
                    high_risk_apps[package] = {
                        'risk_categories': risk_categories,
                        'frequency': package_freq.get(package, 1)
                    }

        # 统计高频应用（Top 50）
        package_counts = pd.Series(all_packages).value_counts().head(50)

        # 高风险应用按频次排序
        sorted_high_risk = sorted(
            high_risk_apps.items(),
            key=lambda x: x[1]['frequency'],
            reverse=True
        )
        top_high_risk = sorted_high_risk[:20]  # 取前20个

        # 识别高风险应用类型分布
        risk_type_counts = {}
        for app_info in high_risk_apps.values():
            for category in app_info['risk_categories']:
                risk_type_counts[category] = risk_type_counts.get(category, 0) + 1

        return {
            'app_count_stats': {
                'mean': float(np.mean(app_counts)),
                'median': float(np.median(app_counts)),
                'min': int(min(app_counts)) if app_counts else 0,
                'max': int(max(app_counts)) if app_counts else 0
            },
            'top_packages': package_counts.to_dict(),
            'high_risk_apps': {
                package: {
                    'risk_categories': info['risk_categories'],
                    'installation_count': info['frequency']
                } for package, info in top_high_risk
            },
            'high_risk_app_types': list(risk_type_counts.keys()),
            'high_risk_app_type_distribution': risk_type_counts,
            'total_high_risk_apps': len(high_risk_apps),
            'high_risk_app_ratio': len(high_risk_apps) / len(set(all_packages)) if all_packages else 0,
            'classification_method': 'KEYWORD_FALLBACK'
        }

    def _summarize_apps(self, json_data_list: List[Dict]) -> Dict:
        """应用列表统计 - 入口方法，优先使用LLM分类"""
        return self._summarize_apps_with_llm_classification(json_data_list)

    def _summarize_fdc(self, json_data_list: List[Dict]) -> Dict:
        """FDC数据统计"""
        query_3days = []
        query_7days = []
        query_30days = []
        query_90days = []
        query_180days = []
        query_360days = []

        loan_counts = []
        outstanding_balances = []
        active_platform_counts = []
        max_dpds = []

        for data in json_data_list:
            # ⚠️ 修复：FDC在params里面，不是根级别
            fdc = data.get('params', {}).get('FDC', {})
            history = fdc.get('history_inquiry', {})

            # 防御性检查：确保stats是dict
            stats = history.get('statistic', {})
            if not isinstance(stats, dict):
                stats = {}

            query_3days.append(stats.get('3_hari', 0))
            query_7days.append(stats.get('7_hari', 0))
            query_30days.append(stats.get('30_hari', 0))
            query_90days.append(stats.get('90_hari', 0))
            query_180days.append(stats.get('180_hari', 0))
            query_360days.append(stats.get('360_hari', 0))

            # 防御性检查：确保pinjaman是list
            pinjaman = fdc.get('pinjaman', [])
            if not isinstance(pinjaman, list):
                pinjaman = []
            loan_counts.append(len(pinjaman))

            balance = sum(p.get('sisa_pinjaman_berjalan', 0) for p in pinjaman)
            outstanding_balances.append(balance)

            # 防御性检查：确保platforms是dict
            platforms = fdc.get('platform_aktif', {})
            if not isinstance(platforms, dict):
                platforms = {}
            # 强制转为int，防止字符串类型问题
            active_count = platforms.get('jumlahPlatformAktif', 0)
            try:
                active_platform_counts.append(int(active_count))
            except (ValueError, TypeError):
                active_platform_counts.append(0)

            dpds = [p.get('dpd_max', 0) for p in pinjaman]
            max_dpds.append(max(dpds) if dpds else 0)

        return {
            'query_frequency': {
                'last_3days': float(np.mean(query_3days)),
                'last_7days': float(np.mean(query_7days)),
                'last_30days': float(np.mean(query_30days)),
                'last_90days': float(np.mean(query_90days)),
                'last_180days': float(np.mean(query_180days)),
                'last_360days': float(np.mean(query_360days))
            },
            'loan_stats': {
                'avg_count': float(np.mean(loan_counts)),
                'max_count': int(max(loan_counts)) if loan_counts else 0,
                'avg_outstanding_balance': float(np.mean(outstanding_balances))
            },
            'active_platforms': float(np.mean(active_platform_counts)),
            'dpd_stats': {
                'avg_max_dpd': float(np.mean(max_dpds)),
                'dpd_30plus_ratio': sum(1 for d in max_dpds if d >= 30) / len(max_dpds) if max_dpds else 0,
                'dpd_60plus_ratio': sum(1 for d in max_dpds if d >= 60) / len(max_dpds) if max_dpds else 0,
                'dpd_90plus_ratio': sum(1 for d in max_dpds if d >= 90) / len(max_dpds) if max_dpds else 0
            }
        }

    def analyze_with_llm(self, analysis_data: Dict) -> Dict:
        """
        调用qwen3.6-plus进行深度分析
        注意：只发送统计摘要，不发送原始JSON数据

        Args:
            analysis_data: 准备好的分析数据（包含stats和sample_summary）

        Returns:
            LLM分析结果
        """
        logger.info("调用qwen3.6-plus进行深度分析...")

        # ⚠️ 关键修复：只发送统计摘要，不发送原始JSON
        # 原始analysis_data包含json_data_list会导致prompt过大
        prompt_data = {
            'overall_stats': analysis_data['stats'],  # 总体统计
            'sample_summary': analysis_data['sample_summary']  # 样本摘要（已聚合）
        }

        logger.info(f"发送统计数据: 样本数={len(analysis_data.get('json_data_list', []))}, "
                   f"摘要字段={list(prompt_data['sample_summary'].keys())}")

        # 估算token数量（粗略估计：每个字符约0.3 token）
        prompt_size = len(custom_json_dumps(prompt_data))
        estimated_tokens = int(prompt_size * 0.3)
        logger.info(f"预计token消耗: ~{estimated_tokens} tokens (prompt size: {prompt_size} chars)")

        # 使用模板渲染prompt
        prompt_template_path = os.path.join(
            os.path.dirname(__file__), '..', 'prompts', 'data_analysis_template.txt'
        )

        try:
            # 直接构造prompt，不使用模板
            prompt_json = custom_json_dumps(prompt_data, ensure_ascii=False, indent=2)
            logger.info(f"发送统计数据: {len(prompt_json)} 字符, ~{int(len(prompt_json)*0.3)} tokens")

            # 构造system prompt
            system_prompt = """你是一个专业的印尼现金贷风控数据分析师。请分析以下统计数据，形成结构化的业务知识库。

**必须严格遵守**:
1. 只返回有效的JSON - 不要返回任何Markdown格式
2. 不要有任何解释文字 - 只返回纯JSON对象
3. 基于实际提供的数据分析，不要编造
4. 所有数值保留4位小数
"""

            # 构造user prompt
            user_prompt = f"""请分析以下印尼现金贷业务数据：

{prompt_json}

请严格按照以下JSON格式输出分析结果：

{{
  "knowledge_base": {{
    "summary": {{
      "total_samples": 2272,
      "overdue_rate": 0.7245,
      "analysis_date": "2026-04-26"
    }},
    "base_analysis": {{
      "gender_risk": {{
        "male_overdue_rate": 0.718,
        "female_overdue_rate": 0.729,
        "risk_ratio": 0.9849
      }},
      "age_risk_bins": [
        {{"bin": "20-25", "overdue_rate": 0.76}},
        {{"bin": "26-30", "overdue_rate": 0.74}}
      ],
      "income_risk_correlation": -0.32,
      "job_risk_distribution": {{"16": 0.74, "12": 0.71}},
      "marriage_risk": {{"1": 0.74, "2": 0.71}},
      "children_risk": {{"0": 0.72, "1": 0.70}},
      "work_years_risk_correlation": -0.28
    }},
    "app_analysis": {{
      "avg_app_count": 47.65,
      "max_app_count": 123,
      "min_app_count": 12,
      "app_type_distribution": {{
        "finance": 0.1007,
        "social": 0.22
      }},
      "high_risk_app_types": ["借贷类", "多头借贷聚合类"],
      "high_risk_app_list": ["com.flex.rupiah", "com.adakami.dana"],
      "finance_app_ratio": 0.1007
    }},
    "fdc_analysis": {{
      "query_freq_risk": {{
        "last_3days_avg": 4.2,
        "last_7days_avg": 9.8,
        "last_30days_avg": 21.5
      }},
      "loan_record_stats": {{
        "avg_loan_count": 14.5,
        "max_loan_count": 85,
        "avg_outstanding_balance": 1250000.0,
        "avg_active_platforms": 4.2
      }},
      "dpd_analysis": {{
        "avg_max_dpd": 12.3,
        "dpd_30plus_ratio": 0.145,
        "dpd_60plus_ratio": 0.078,
        "dpd_90plus_ratio": 0.035
      }}
    }},
    "risk_rules": [
      {{
        "rule": "FDC近7天查询次数>10",
        "description": "短期多头借贷风险",
        "risk_level": "high"
      }}
    ]
  }}
}}

现在请分析并返回JSON："""

            # 直接调用LLM
            response = self.llm_client.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0
            )

            # 解析JSON响应 - 尝试清理Markdown标记
            cleaned_response = self._clean_llm_response(response)

            # 解析JSON
            result = json.loads(cleaned_response)
            logger.info("LLM分析完成，成功解析知识库")
            return result

        except Exception as e:
            logger.error(f"LLM分析失败: {e}")
            # 返回默认结构
            return self._get_default_knowledge_base(analysis_data)

    def _clean_llm_response(self, response: str) -> str:
        """清理LLM响应，移除Markdown标记"""
        # 移除```json```标记
        if response.startswith('```json'):
            response = response[7:]
        if response.startswith('```'):
            response = response[3:]
        if response.endswith('```'):
            response = response[:-3]
        return response.strip()

    def run(self, input_data: Dict) -> Dict:
        """
        运行数据分析Agent

        Args:
            input_data: 输入数据
                - short_links: 短链URL列表
                - model_samples: 建模样本DataFrame
                - sample_size: 采样数量（默认100）

        Returns:
            业务知识库JSON
        """
        self.log_start()

        short_links = input_data.get('short_links', [])
        model_samples = input_data.get('model_samples', pd.DataFrame())
        sample_size = input_data.get('sample_size', 100)

        if not short_links or model_samples.empty:
            logger.error("输入数据为空，请提供短链列表和建模样本")
            return {}

        # 1. 加载和准备数据
        analysis_data = self.load_and_prepare_data(short_links, model_samples, sample_size)

        # 2. 调用LLM分析
        knowledge_base = self.analyze_with_llm(analysis_data)

        # 3. 保存输出
        output_file = self.save_output('knowledge_base.json', custom_json_dumps(knowledge_base, ensure_ascii=False, indent=2))

        self.log_end()
        logger.info(f"知识库已保存到: {output_file}")

        return knowledge_base

    def _get_default_knowledge_base(self, analysis_data: Dict) -> Dict:
        """获取默认知识库（LLM失败时的fallback）"""
        return {
            'knowledge_base': {
                'summary': {
                    'total_samples': analysis_data['stats']['total_samples'],
                    'overdue_rate': analysis_data['stats']['overdue_rate'],
                    'analysis_date': datetime.now().strftime('%Y-%m-%d')
                },
                'base_analysis': analysis_data['sample_summary']['base_stats'],
                'app_analysis': analysis_data['sample_summary']['app_stats'],
                'fdc_analysis': analysis_data['sample_summary']['fdc_stats'],
                'risk_rules': [
                    {
                        'rule': 'default_rule',
                        'description': 'LLM分析失败，使用默认规则',
                        'risk_level': 'medium'
                    }
                ]
            }
        }

    def _calc_age(self, birthday_str: str) -> int:
        """计算年龄"""
        try:
            birth_parts = birthday_str.split('-')
            if len(birth_parts) == 3:
                birth_year = int(birth_parts[2])
                current_year = datetime.now().year
                return current_year - birth_year
        except:
            pass
        return 0


def main():
    """主函数 - 测试用"""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

    from data.data_loader import DataLoader

    logging.basicConfig(level=logging.INFO)

    agent = DataAnalysisAgent()
    loader = DataLoader()

    # 加载数据
    short_links = loader.load_short_links()
    model_samples = loader.load_model_samples()

    # 运行分析（只用10条样本测试）
    result = agent.run({
        'short_links': short_links,
        'model_samples': model_samples,
        'sample_size': 10
    })

    print(json.dumps(result, ensure_ascii=False, indent=2)[:2000])


if __name__ == '__main__':
    main()
