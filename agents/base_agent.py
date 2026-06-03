"""
Agent基类
所有Agent的基类，提供通用功能
"""

import os
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional
from datetime import datetime

from utils.llm_client import LLMClient

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Agent基类"""

    def __init__(self, name: str, config_path: Optional[str] = None):
        """
        初始化Agent

        Args:
            name: Agent名称
            config_path: 配置文件路径
        """
        self.name = name
        self.config_path = config_path
        self.llm_client = LLMClient(config_path)
        self.output_dir = self._get_output_dir()

        logger.info(f"Agent '{name}' 初始化完成")

    def _get_output_dir(self) -> str:
        """获取输出目录"""
        base_output = os.path.join(os.path.dirname(__file__), '..', 'outputs')
        agent_output_map = {
            'data_analysis': 'knowledge_base',
            'feature_design': 'feature_design',
            'feature_engineering': 'feature_code',
            'feature_review': 'feature_code',
            'feature_evaluation': 'evaluation',
            'feature_deployment': 'deployment'
        }
        subdir = agent_output_map.get(self.name, '')
        if subdir:
            output_path = os.path.join(base_output, subdir)
            os.makedirs(output_path, exist_ok=True)
            return output_path
        return base_output

    def save_output(self, filename: str, data) -> str:
        """
        保存输出文件

        Args:
            filename: 文件名
            data: 数据（字典或字符串）

        Returns:
            文件路径
        """
        filepath = os.path.join(self.output_dir, filename)

        if isinstance(data, dict):
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        elif isinstance(data, str):
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(data)
        else:
            raise ValueError(f"不支持的数据类型: {type(data)}")

        logger.info(f"保存输出文件: {filepath}")
        return filepath

    def load_input(self, filename: str) -> Dict:
        """
        加载输入文件

        Args:
            filename: 文件名

        Returns:
            数据字典
        """
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    @abstractmethod
    def run(self, input_data: Dict) -> Dict:
        """
        运行Agent

        Args:
            input_data: 输入数据

        Returns:
            输出数据
        """
        pass

    def log_start(self):
        """记录开始日志"""
        logger.info(f"="*60)
        logger.info(f"Agent '{self.name}' 开始执行 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"="*60)

    def log_end(self):
        """记录结束日志"""
        logger.info(f"="*60)
        logger.info(f"Agent '{self.name}' 执行完成 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"="*60)
