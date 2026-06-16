"""Project management API routes."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.auth.deps import get_current_user
from backend.models.user import User
from backend.services.project_service import (
    create_project,
    enable_active_templates,
    get_default_project,
    get_project,
    list_project_templates,
    set_project_template_selection,
    list_projects,
    set_project_template_enabled,
    soft_delete_project,
    update_project,
)
from backend.services.template_library import get_template

router = APIRouter()


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    business_line: str = ""
    country: str = ""
    product: str = ""
    description: str = ""
    config: Optional[dict] = None
    template_ids: Optional[list[str]] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    business_line: Optional[str] = None
    country: Optional[str] = None
    product: Optional[str] = None
    description: Optional[str] = None
    config: Optional[dict] = None
    status: Optional[str] = None


class ProjectTemplateUpdate(BaseModel):
    enabled: bool = True
    config_override: Optional[dict] = None


class ProjectTemplateSelectionUpdate(BaseModel):
    template_ids: list[str] = []


@router.get("")
def api_list_projects(
    status: Optional[str] = Query(default="active"),
    db: Session = Depends(get_db),
) -> dict:
    items = [p.to_dict() for p in list_projects(db, status=status)]
    return {"items": items, "total": len(items)}


@router.post("")
def api_create_project(
    body: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    project = create_project(
        db,
        name=body.name,
        business_line=body.business_line,
        country=body.country,
        product=body.product,
        description=body.description,
        config=body.config,
        owner_user_id=current_user.id,
    )
    if body.template_ids is None:
        enable_active_templates(db, project.id)
        db.commit()
        db.refresh(project)
    else:
        set_project_template_selection(db, project.id, body.template_ids, selected_by=current_user.id)
    return project.to_dict()


@router.get("/default")
def api_default_project(db: Session = Depends(get_db)) -> dict:
    return get_default_project(db).to_dict()


@router.get("/{project_id}")
def api_project_detail(project_id: int, db: Session = Depends(get_db)) -> dict:
    project = get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")
    return project.to_dict()


@router.patch("/{project_id}")
def api_update_project(project_id: int, body: ProjectUpdate, db: Session = Depends(get_db)) -> dict:
    project = get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")
    payload = body.model_dump(exclude_unset=True) if hasattr(body, "model_dump") else body.dict(exclude_unset=True)
    return update_project(db, project, payload).to_dict()


@router.delete("/{project_id}")
def api_delete_project(project_id: int, db: Session = Depends(get_db)) -> dict:
    project = get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")
    try:
        return soft_delete_project(db, project).to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{project_id}/templates")
def api_project_templates(
    project_id: int,
    enabled: Optional[bool] = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    project = get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")
    rows = list_project_templates(db, project_id, enabled=enabled)
    items = [row.to_dict() for row in rows]
    return {"items": items, "total": len(items)}


@router.put("/{project_id}/templates")
def api_set_project_template_selection(
    project_id: int,
    body: ProjectTemplateSelectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    project = get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")
    rows = set_project_template_selection(db, project_id, body.template_ids, selected_by=current_user.id)
    items = [row.to_dict() for row in rows if row.enabled]
    return {"items": items, "total": len(items)}


@router.post("/{project_id}/templates/sync-active")
def api_sync_active_templates(project_id: int, db: Session = Depends(get_db)) -> dict:
    project = get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")
    inserted = enable_active_templates(db, project_id)
    db.commit()
    return {"project_id": project_id, "inserted": inserted}


@router.post("/{project_id}/templates/{template_id}")
def api_set_project_template(
    project_id: int,
    template_id: str,
    body: ProjectTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    project = get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")
    template = get_template(db, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在")
    row = set_project_template_enabled(
        db,
        project_id=project.id,
        template_db_id=template.id,
        enabled=body.enabled,
        selected_by=current_user.id,
        config_override=body.config_override,
    )
    return row.to_dict()
