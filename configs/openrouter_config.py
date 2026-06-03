"""
OpenRouter API配置
"""

import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# OpenRouter配置
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# 模型配置
DEFAULT_MODEL = "qwen/qwen3.6-plus"

# LLM参数
DEFAULT_TEMPERATURE = 0
DEFAULT_MAX_TOKENS = 8000
MAX_RETRIES = 3
RETRY_DELAY = 2


def get_openrouter_client():
    """获取OpenRouter客户端"""
    from openai import OpenAI

    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY 未配置")

    return OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL
    )
