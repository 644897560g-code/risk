"""Task and TaskLog SQLAlchemy models"""
import json
from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from backend.app.database import Base


class Task(Base):
    """任务记录 — 每次特征挖掘执行"""

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, default="")
    mode = Column(String(50), nullable=False, default="normal")  # normal | template_task
    status = Column(String(50), nullable=False, default="pending")  # pending | running | completed | failed | cancelled
    progress = Column(Float, nullable=False, default=0.0)  # 0.0 ~ 100.0

    # 任务配置（JSON 格式存储数据路径等）
    config = Column(JSON, nullable=True)

    # 模板任务关联
    linked_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)  # template_task 关联的普通任务ID

    # 结果
    total_features = Column(Integer, nullable=True)
    passed_features = Column(Integer, nullable=True)
    deployed_version = Column(String(50), nullable=True)

    # 错误信息
    error_message = Column(Text, nullable=True)

    # 计划执行时间（用户可配置）
    scheduled_at = Column(DateTime, nullable=True)

    # 时间
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # 关联
    logs = relationship("TaskLog", back_populates="task", cascade="all, delete-orphan",
                        order_by="TaskLog.timestamp")

    def _iso_z(self, dt) -> str | None:
        """序列化为 ISO 格式并标记 UTC（+Z 后缀）"""
        if dt is None:
            return None
        return dt.isoformat() + "Z"

    def to_dict(self, include_logs: bool = False) -> dict:
        d = {
            "id": self.id,
            "name": self.name,
            "mode": self.mode,
            "status": self.status,
            "progress": self.progress,
            "linked_task_id": self.linked_task_id,
            "total_features": self.total_features,
            "passed_features": self.passed_features,
            "deployed_version": self.deployed_version,
            "error_message": self.error_message,
            "config": self.config,
            "scheduled_at": self._iso_z(self.scheduled_at),
            "created_at": self._iso_z(self.created_at),
            "started_at": self._iso_z(self.started_at),
            "completed_at": self._iso_z(self.completed_at),
        }
        if include_logs:
            d["logs"] = [log.to_dict() for log in self.logs]
        return d


class TaskLog(Base):
    """任务日志条目"""

    __tablename__ = "task_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    level = Column(String(20), nullable=False, default="info")  # info | warning | error
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)

    task = relationship("Task", back_populates="logs")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "level": self.level,
            "message": self.message,
            "timestamp": (self.timestamp.isoformat() + "Z") if self.timestamp else None,
        }
