"""Template library API routes backed by PostgreSQL."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.services.template_library import (
    ACTIVE_STATUS,
    PENDING_STATUS,
    find_template_code,
    get_template,
    list_dimensions,
    list_templates,
    template_to_channel1_item,
    template_to_dict,
    template_to_pending_item,
)

router = APIRouter()


class Channel1Template(BaseModel):
    template_id: str
    template_name: str
    dimension: str
    description: str = ""
    dsl: str
    python_function: str
    python_code: str = ""


class Channel1ListResponse(BaseModel):
    items: List[dict]
    total: int


class PendingListResponse(BaseModel):
    items: List[dict]
    total: int


@router.get("/dimensions")
def api_template_dimensions(db: Session = Depends(get_db)) -> dict:
    """List active template dimensions."""
    items = [d.to_dict() for d in list_dimensions(db)]
    return {"items": items, "total": len(items)}


@router.get("")
def api_list_templates(
    status: Optional[str] = Query(default=None),
    source_channel: Optional[int] = Query(default=None),
    dimension: Optional[str] = Query(default=None),
    keyword: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """List templates from the unified template library."""
    items = list_templates(
        db,
        status=status,
        source_channel=source_channel,
        dimension=dimension,
        keyword=keyword,
    )
    return {"items": [template_to_dict(t) for t in items], "total": len(items)}


@router.get("/channel1")
def api_list_channel1_templates(db: Session = Depends(get_db)) -> Channel1ListResponse:
    """Compatibility endpoint: list active templates."""
    items = list_templates(db, status=ACTIVE_STATUS)
    mapped = [template_to_channel1_item(t) for t in items]
    return Channel1ListResponse(items=mapped, total=len(mapped))


@router.get("/channel2-pending")
def api_list_channel2_pending(db: Session = Depends(get_db)) -> PendingListResponse:
    """Compatibility endpoint: list pending templates."""
    items = list_templates(db, status=PENDING_STATUS)
    mapped = [template_to_pending_item(t) for t in items]
    return PendingListResponse(items=mapped, total=len(mapped))


@router.get("/{template_id}")
def api_template_detail(template_id: str, db: Session = Depends(get_db)) -> dict:
    template = get_template(db, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在")
    return template_to_dict(template)


@router.get("/channel1/{template_id}/code")
def api_channel1_template_code(template_id: str, db: Session = Depends(get_db)) -> dict:
    """Get full Python function source for an active template."""
    template = get_template(db, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在")
    return {"template_id": template_id, "code": find_template_code(template)}
