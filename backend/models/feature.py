"""Feature version and metric SQLAlchemy models"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, ForeignKey

from backend.app.database import Base


class FeatureVersion(Base):
    """特征版本记录 — 每次部署产出版本"""

    __tablename__ = "feature_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(String(50), nullable=False, unique=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    task_id = Column(Integer, nullable=True)  # 关联的Task ID
    total_features = Column(Integer, nullable=False, default=0)
    passed_features = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "version": self.version,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "total_features": self.total_features,
            "passed_features": self.passed_features,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class FeatureMetric(Base):
    """单个特征在某个版本的评估指标"""  # 用于 ECharts 可视化

    __tablename__ = "feature_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(String(50), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    task_id = Column(Integer, nullable=True)
    feature_name = Column(String(255), nullable=False)
    iv = Column(Float, nullable=True)
    psi = Column(Float, nullable=True)
    coverage = Column(Float, nullable=True)
    is_passed = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "version": self.version,
            "project_id": self.project_id,
            "feature_name": self.feature_name,
            "iv": self.iv,
            "psi": self.psi,
            "coverage": self.coverage,
            "is_passed": bool(self.is_passed),
        }
