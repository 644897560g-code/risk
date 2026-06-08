"""
LLM客户端封装 - 通过OpenRouter接入qwen3.6-plus
支持流式输出、错误重试、prompt模板管理
"""

import os
import time
import logging
from typing import Optional, Dict, List
from openai import OpenAI
from jinja2 import Template
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

logger = logging.getLogger(__name__)


class LLMClient:
    """OpenRouter qwen3.6-plus LLM客户端"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化LLM客户端

        Args:
            config_path: 配置文件路径（可选）
        """
        # 从环境变量获取配置
        self.api_key = os.getenv("OPENROUTER_API_KEY", "")
        self.base_url = "https://openrouter.ai/api/v1"
        self.model = os.getenv("LLM_MODEL", "qwen/qwen3.6-plus")

        # 默认参数
        self.temperature = 0
        self.max_tokens = 8000
        self.max_retries = 3
        self.retry_delay = 2

        if not self.api_key:
            raise ValueError(
                "OPENROUTER_API_KEY 未配置。请在后端进程环境变量或 .env 中设置；"
                "如果使用 Docker Compose，请确保 docker-compose.yml 将 OPENROUTER_API_KEY 传给 backend。"
            )

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=120.0  # 120秒请求超时，避免无限挂起
        )

    def chat(self, messages: List[Dict[str, str]], temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> str:
        """
        发送聊天请求

        Args:
            messages: 消息列表，格式 [{"role": "user", "content": "..."}]
            temperature: 温度参数，默认使用配置值
            max_tokens: 最大token数，默认使用配置值

        Returns:
            LLM响应内容
        """
        if temperature is None:
            temperature = self.temperature
        if max_tokens is None:
            max_tokens = self.max_tokens

        for attempt in range(self.max_retries):
            try:
                logger.info(f"调用LLM (model={self.model}, temperature={temperature}, max_tokens={max_tokens})...")

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )

                result = response.choices[0].message.content
                logger.info(f"LLM调用成功，返回 {len(result)} 字符")
                return result

            except Exception as e:
                logger.error(f"LLM调用失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise Exception(f"LLM调用失败，已重试{self.max_retries}次: {e}")

    def chat_stream(self, messages: List[Dict[str, str]], temperature: Optional[float] = None, max_tokens: Optional[int] = None):
        """
        流式聊天请求 — 逐块 yield 文本内容

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数

        Yields:
            str: 每块文本
        """
        import json

        if temperature is None:
            temperature = self.temperature
        if max_tokens is None:
            max_tokens = self.max_tokens

        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                )

                for chunk in response:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta and delta.content:
                        yield delta.content
                return  # 成功完成

            except Exception as e:
                logger.error(f"LLM流式调用失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    yield f"\n\n[错误: LLM调用失败 - {e}]"

    def chat_with_template(self, template_path: str, data: Dict, temperature: Optional[float] = None) -> str:
        """
        使用模板发送聊天请求

        Args:
            template_path: 模板文件路径
            data: 模板数据
            temperature: 温度参数

        Returns:
            LLM响应内容
        """
        template_str = self._load_template(template_path)
        prompt = Template(template_str).render(data)

        return self.chat([{"role": "user", "content": prompt}], temperature)

    def _load_template(self, template_path: str) -> str:
        """加载模板文件"""
        full_path = os.path.join(os.path.dirname(__file__), '..', 'prompts', template_path)
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()


class PromptTemplate:
    """Prompt模板管理器"""

    def __init__(self, templates_dir: Optional[str] = None):
        if templates_dir is None:
            templates_dir = os.path.join(os.path.dirname(__file__), '..', 'prompts')
        self.templates_dir = templates_dir

    def render(self, template_name: str, **kwargs) -> str:
        """
        渲染模板

        Args:
            template_name: 模板名称
            **kwargs: 模板变量

        Returns:
            渲染后的prompt
        """
        template_path = os.path.join(self.templates_dir, template_name)
        with open(template_path, 'r', encoding='utf-8') as f:
            template_str = f.read()

        return Template(template_str).render(**kwargs)


# 便捷函数
def create_llm_client() -> LLMClient:
    """创建LLM客户端实例"""
    return LLMClient()
