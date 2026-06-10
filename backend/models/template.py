"""Template library SQLAlchemy models."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from backend.app.database import Base


class TemplateDimension(Base):
    """Platform-level template dimension taxonomy."""

    __tablename__ = "template_dimensions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dimension_code = Column(String(50), nullable=False, unique=True, index=True)
    dimension_id = Column(String(20), nullable=True, unique=True)
    dimension_name_cn = Column(String(100), nullable=False, default="")
    description = Column(Text, nullable=False, default="")
    sort_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    templates = relationship("Template", back_populates="dimension")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "dimension_code": self.dimension_code,
            "dimension_id": self.dimension_id,
            "dimension_name_cn": self.dimension_name_cn,
            "description": self.description,
            "sort_order": self.sort_order,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Template(Base):
    """Template library record with lifecycle state."""

    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    template_id = Column(String(50), nullable=False, unique=True, index=True)
    template_name = Column(String(100), nullable=False)
    template_name_cn = Column(String(100), nullable=False, default="")
    dimension_id = Column(Integer, ForeignKey("template_dimensions.id"), nullable=False)
    source_channel = Column(Integer, nullable=False, default=1)
    source = Column(String(100), nullable=False, default="")
    status = Column(String(30), nullable=False, default="pending")
    complexity = Column(String(30), nullable=False, default="")
    description = Column(Text, nullable=False, default="")
    dsl = Column(Text, nullable=False, default="")
    dsl_description = Column(Text, nullable=False, default="")
    parameter_space = Column(JSON, nullable=True)
    formula_template = Column(Text, nullable=False, default="")
    python_function = Column(String(100), nullable=False, default="")
    python_code = Column(Text, nullable=False, default="")
    python_module = Column(String(100), nullable=False, default="")
    examples = Column(JSON, nullable=True)
    quality_checks = Column(JSON, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    submitted_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    dimension = relationship("TemplateDimension", back_populates="templates")
    review_histories = relationship(
        "TemplateReviewHistory",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="TemplateReviewHistory.created_at",
    )

    def to_dict(self) -> dict:
        dimension = self.dimension
        return {
            "id": self.id,
            "template_id": self.template_id,
            "template_name": self.template_name,
            "template_name_cn": self.template_name_cn,
            "dimension_id": self.dimension_id,
            "dimension": dimension.dimension_code if dimension else None,
            "dimension_name_cn": dimension.dimension_name_cn if dimension else None,
            "source_channel": self.source_channel,
            "source": self.source,
            "status": self.status,
            "complexity": self.complexity,
            "description": self.description,
            "dsl": self.dsl,
            "dsl_description": self.dsl_description,
            "parameter_space": self.parameter_space,
            "formula_template": self.formula_template,
            "python_function": self.python_function,
            "python_code": self.python_code,
            "python_module": self.python_module,
            "examples": self.examples,
            "quality_checks": self.quality_checks,
            "metadata": self.metadata_json,
            "version": self.version,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "rejected_at": self.rejected_at.isoformat() if self.rejected_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class TemplateReviewHistory(Base):
    """Audit trail for template review decisions."""

    __tablename__ = "template_review_histories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    template_db_id = Column(Integer, ForeignKey("templates.id", ondelete="CASCADE"), nullable=False)
    action = Column(String(30), nullable=False)
    reason = Column(Text, nullable=False, default="")
    reviewer = Column(String(100), nullable=False, default="")
    source_channel = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    template = relationship("Template", back_populates="review_histories")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "template_id": self.template.template_id if self.template else None,
            "action": self.action,
            "reason": self.reason,
            "reviewer": self.reviewer,
            "source_channel": self.source_channel,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TemplateRejectedMemory(Base):
    """Platform-level rejected-template memory used as generation counterexamples."""

    __tablename__ = "template_rejected_memories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    template_db_id = Column(Integer, ForeignKey("templates.id", ondelete="SET NULL"), nullable=True)
    template_id = Column(String(50), nullable=False, default="")
    template_name = Column(String(100), nullable=False, default="")
    reason = Column(Text, nullable=False)
    source_channel = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "template_id": self.template_id,
            "template_name": self.template_name,
            "reason": self.reason,
            "source_channel": self.source_channel,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
