"""Project models for task and template scoping."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from backend.app.database import Base


class Project(Base):
    """业务项目，用于隔离任务、结果和项目级配置。"""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=False)
    business_line = Column(String(120), nullable=False, default="")
    country = Column(String(50), nullable=False, default="")
    product = Column(String(120), nullable=False, default="")
    description = Column(Text, nullable=False, default="")
    config_json = Column("config", JSON, nullable=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String(30), nullable=False, default="active")
    is_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    tasks = relationship("Task", back_populates="project")
    template_links = relationship(
        "ProjectTemplate",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "business_line": self.business_line,
            "country": self.country,
            "product": self.product,
            "description": self.description,
            "config": self.config_json or {},
            "owner_user_id": self.owner_user_id,
            "status": self.status,
            "is_default": self.is_default,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ProjectTemplate(Base):
    """项目启用的平台模板关联。"""

    __tablename__ = "project_templates"
    __table_args__ = (
        UniqueConstraint("project_id", "template_db_id", name="uq_project_templates_project_template"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    template_db_id = Column(Integer, ForeignKey("templates.id", ondelete="CASCADE"), nullable=False, index=True)
    enabled = Column(Boolean, nullable=False, default=True)
    selected_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    selected_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    config_override = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="template_links")
    template = relationship("Template")

    def to_dict(self) -> dict:
        template = self.template
        return {
            "id": self.id,
            "project_id": self.project_id,
            "template_db_id": self.template_db_id,
            "template_id": template.template_id if template else None,
            "template_name": template.template_name if template else None,
            "template_name_cn": template.template_name_cn if template else None,
            "dimension": template.dimension.dimension_code if template and template.dimension else None,
            "enabled": self.enabled,
            "selected_by": self.selected_by,
            "selected_at": self.selected_at.isoformat() if self.selected_at else None,
            "config_override": self.config_override,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
