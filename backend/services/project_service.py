"""Project CRUD and template selection helpers."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.models.project import Project, ProjectTemplate
from backend.models.template import Template


DEFAULT_PROJECT_ID = 1


def ensure_default_project(db: Session) -> Project:
    """Ensure the bootstrap project exists and active templates are enabled."""
    now = datetime.utcnow()
    project = db.query(Project).filter(Project.id == DEFAULT_PROJECT_ID).first()
    if project is None:
        project = Project(
            id=DEFAULT_PROJECT_ID,
            name="默认项目",
            business_line="印尼现金贷",
            country="INDO",
            product="短期现金贷",
            description="系统初始化创建，用于承载迁移前已有任务和结果。",
            status="active",
            is_default=True,
            created_at=now,
            updated_at=now,
        )
        db.add(project)
        db.flush()
    else:
        project.is_default = True
        project.status = project.status or "active"
        project.updated_at = now

    enable_active_templates(db, project.id)
    db.commit()
    db.refresh(project)
    return project


def list_projects(db: Session, status: str | None = None) -> list[Project]:
    query = db.query(Project)
    if status and status != "all":
        query = query.filter(Project.status == status)
    return query.order_by(Project.is_default.desc(), Project.id.asc()).all()


def get_project(db: Session, project_id: int) -> Project | None:
    return db.query(Project).filter(Project.id == project_id).first()


def get_default_project(db: Session) -> Project:
    project = db.query(Project).filter(Project.is_default.is_(True)).order_by(Project.id).first()
    if project:
        return project
    return ensure_default_project(db)


def create_project(
    db: Session,
    name: str,
    business_line: str = "",
    country: str = "",
    product: str = "",
    description: str = "",
    config: dict[str, Any] | None = None,
    owner_user_id: int | None = None,
) -> Project:
    now = datetime.utcnow()
    project = Project(
        name=name,
        business_line=business_line,
        country=country,
        product=product,
        description=description,
        config_json=config or {},
        owner_user_id=owner_user_id,
        status="active",
        is_default=False,
        created_at=now,
        updated_at=now,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def update_project(db: Session, project: Project, payload: dict[str, Any]) -> Project:
    for field in ["name", "business_line", "country", "product", "description", "status"]:
        if field in payload and payload[field] is not None:
            setattr(project, field, payload[field])
    if "config" in payload and payload["config"] is not None:
        project.config_json = payload["config"]
    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(project)
    return project


def soft_delete_project(db: Session, project: Project) -> Project:
    if project.is_default:
        raise ValueError("default project cannot be deleted")
    project.status = "deleted"
    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(project)
    return project


def enable_active_templates(db: Session, project_id: int) -> int:
    """Enable all active platform templates for a project if missing."""
    active_templates = db.query(Template).filter(Template.status == "active").all()
    existing = {
        row.template_db_id
        for row in db.query(ProjectTemplate).filter(ProjectTemplate.project_id == project_id).all()
    }
    now = datetime.utcnow()
    inserted = 0
    for template in active_templates:
        if template.id in existing:
            continue
        db.add(
            ProjectTemplate(
                project_id=project_id,
                template_db_id=template.id,
                enabled=True,
                selected_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        inserted += 1
    db.flush()
    return inserted


def list_project_templates(db: Session, project_id: int, enabled: bool | None = None) -> list[ProjectTemplate]:
    query = (
        db.query(ProjectTemplate)
        .join(Template, ProjectTemplate.template_db_id == Template.id)
        .filter(ProjectTemplate.project_id == project_id)
    )
    if enabled is not None:
        query = query.filter(ProjectTemplate.enabled.is_(enabled))
    return query.order_by(Template.created_at.asc(), Template.template_id.asc(), ProjectTemplate.id.asc()).all()


def set_project_template_enabled(
    db: Session,
    project_id: int,
    template_db_id: int,
    enabled: bool,
    selected_by: int | None = None,
    config_override: dict[str, Any] | None = None,
) -> ProjectTemplate:
    row = (
        db.query(ProjectTemplate)
        .filter(
            ProjectTemplate.project_id == project_id,
            ProjectTemplate.template_db_id == template_db_id,
        )
        .first()
    )
    now = datetime.utcnow()
    if row is None:
        row = ProjectTemplate(
            project_id=project_id,
            template_db_id=template_db_id,
            created_at=now,
        )
        db.add(row)
    row.enabled = enabled
    row.selected_by = selected_by
    row.selected_at = now
    row.updated_at = now
    if config_override is not None:
        row.config_override = config_override
    db.commit()
    db.refresh(row)
    return row


def set_project_template_selection(
    db: Session,
    project_id: int,
    template_ids: list[str],
    selected_by: int | None = None,
) -> list[ProjectTemplate]:
    """Set enabled templates for a project by platform template_id."""
    selected = set(template_ids or [])
    active_templates = db.query(Template).filter(Template.status == "active").all()
    existing = {
        row.template_db_id: row
        for row in db.query(ProjectTemplate).filter(ProjectTemplate.project_id == project_id).all()
    }
    now = datetime.utcnow()
    rows: list[ProjectTemplate] = []
    for template in active_templates:
        row = existing.get(template.id)
        if row is None:
            row = ProjectTemplate(
                project_id=project_id,
                template_db_id=template.id,
                created_at=now,
            )
            db.add(row)
        row.enabled = template.template_id in selected
        row.selected_by = selected_by
        row.selected_at = now
        row.updated_at = now
        rows.append(row)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows
