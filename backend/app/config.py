"""Backend configuration — loaded from environment with sensible defaults"""
import os
from typing import List
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings, loaded from .env or environment variables"""

    # --- Database ---
    database_url: str

    # --- Celery / Redis ---
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    celery_broker_url: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    celery_result_backend: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

    # --- Paths ---
    project_root: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    data_dir: str = os.path.join(project_root, "data")
    output_dir: str = os.path.join(project_root, "outputs")
    deployment_dir: str = os.path.join(output_dir, "deployment")
    evaluation_dir: str = os.path.join(output_dir, "evaluation")
    delivery_dir: str = os.path.join(output_dir, "delivery")

    # --- CORS ---
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"]

    # --- JWT Auth ---
    jwt_secret: str = os.getenv("JWT_SECRET", "change-me-in-production")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours

    # --- API ---
    api_key: str = os.getenv("API_KEY", "")
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # .env has LLM keys — skip them


@lru_cache()
def get_settings() -> Settings:
    return Settings()
