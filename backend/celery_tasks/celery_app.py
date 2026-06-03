"""Celery application configuration"""
import os
import sys

# 确保项目根目录在sys.path中，celery worker能导入agent代码
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from celery import Celery
from backend.app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "feature_mining",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["backend.celery_tasks.agent_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600 * 24 * 7,  # 结果保留7天
)
