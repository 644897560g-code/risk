"""
数据加载器
负责从不同来源加载数据：短链JSON、Excel文件等
"""

import os
import json
import requests
import pandas as pd
from typing import List, Dict, Optional
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ShortLinkFetcher:
    """短链数据获取器"""

    def __init__(self, timeout: int = 30):
        """
        初始化短链获取器

        Args:
            timeout: 请求超时时间（秒）
        """
        self.timeout = timeout
        self.session = requests.Session()

    def fetch_json(self, url: str) -> Optional[Dict]:
        """
        从短链URL获取JSON数据

        Args:
            url: 短链URL

        Returns:
            JSON数据字典，失败返回None
        """
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"获取短链数据失败 [{url}]: {e}")
            return None

    def fetch_batch(self, urls: List[str]) -> List[Dict]:
        """
        批量获取短链JSON数据

        Args:
            urls: 短链URL列表

        Returns:
            JSON数据列表
        """
        results = []
        for i, url in enumerate(urls):
            logger.info(f"获取第 {i+1}/{len(urls)} 条数据: {url}")
            data = self.fetch_json(url)
            if data:
                results.append(data)
        return results


class DataLoader:
    """数据加载器"""

    def __init__(self, base_dir: Optional[str] = None):
        """
        初始化数据加载器

        Args:
            base_dir: 数据文件基础目录
        """
        if base_dir is None:
            base_dir = os.path.dirname(os.path.dirname(__file__))
        self.base_dir = base_dir

    def load_short_links(self, file_path: Optional[str] = None) -> List[str]:
        """
        加载短链文件

        Args:
            file_path: 短链文件路径，默认使用项目根目录的文件

        Returns:
            短链URL列表
        """
        if file_path is None:
            file_path = os.path.join(self.base_dir, '0421全样本短链.txt')

        with open(file_path, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]

        logger.info(f"加载了 {len(urls)} 条短链")
        return urls

    def load_model_samples(self, file_path: Optional[str] = None) -> pd.DataFrame:
        """
        加载建模样本数据

        Args:
            file_path: Excel文件路径

        Returns:
            DataFrame
        """
        if file_path is None:
            file_path = os.path.join(self.base_dir, '印尼模型分_2026_04_21_建模样本aiagent.xlsx')

        df = pd.read_excel(file_path)
        logger.info(f"加载建模样本: {df.shape[0]} 行, {df.shape[1]} 列")
        return df

    def load_fdc_variables(self, file_path: Optional[str] = None) -> pd.DataFrame:
        """
        加载FDC变量清单

        Args:
            file_path: Excel文件路径

        Returns:
            DataFrame
        """
        if file_path is None:
            file_path = os.path.join(self.base_dir, 'FDC4710变量.xlsx')

        df = pd.read_excel(file_path)
        logger.info(f"加载FDC变量清单: {df.shape[0]} 个特征")
        return df

    def load_sample_json(self, file_path: Optional[str] = None) -> Dict:
        """
        加载样例JSON文件

        Args:
            file_path: JSON文件路径

        Returns:
            JSON数据字典
        """
        if file_path is None:
            file_path = os.path.join(self.base_dir, 'id002luzt202603090951432723072')

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        logger.info(f"加载样例JSON: {file_path}")
        return data

    def merge_samples_with_labels(self, samples_df: pd.DataFrame,
                                   json_data_list: List[Dict],
                                   order_id_key: str = 'orderId') -> pd.DataFrame:
        """
        合并样本数据与好坏标签

        Args:
            samples_df: 建模样本DataFrame（包含order_no和is_overdue）
            json_data_list: JSON数据列表
            order_id_key: 订单ID字段名

        Returns:
            合并后的DataFrame
        """
        # 从samples_df中提取订单号和标签
        labels_df = samples_df[['source_order_no', 'is_overdue']].copy()
        labels_df.rename(columns={'source_order_no': order_id_key}, inplace=True)

        # 从JSON数据中提取orderId和关键信息
        records = []
        for data in json_data_list:
            record = {
                order_id_key: data.get(order_id_key),
                'country': data.get('country'),
                'apply_time': data.get('params', {}).get('base', {}).get('applyTime'),
                'json_data': data  # 保存完整JSON供后续使用
            }
            records.append(record)

        json_df = pd.DataFrame(records)

        # 合并
        merged_df = pd.merge(json_df, labels_df, on=order_id_key, how='inner')
        logger.info(f"合并后数据: {merged_df.shape[0]} 行")

        return merged_df


# 便捷函数
def load_all_data() -> tuple:
    """加载所有数据"""
    loader = DataLoader()
    short_links = loader.load_short_links()
    model_samples = loader.load_model_samples()
    fdc_variables = loader.load_fdc_variables()
    sample_json = loader.load_sample_json()

    return short_links, model_samples, fdc_variables, sample_json
