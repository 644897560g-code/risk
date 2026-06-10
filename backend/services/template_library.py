"""Template library persistence and lifecycle helpers."""
from __future__ import annotations

import ast
import os
import re
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.models.template import (
    Template,
    TemplateDimension,
    TemplateRejectedMemory,
    TemplateReviewHistory,
)


ACTIVE_STATUS = "active"
PENDING_STATUS = "pending"
REJECTED_STATUS = "rejected"

DIMENSION_FALLBACKS = {
    "applist": "structure",
    "fdc": "volume",
    "base": "consistency",
    "behavior": "change",
    "custom": "derived",
}


def template_to_dict(template: Template, include_code: bool = True) -> dict:
    data = template.to_dict()
    data["dimension"] = data.get("dimension") or ""
    data["created_at"] = data.get("created_at") or ""
    if not include_code:
        data.pop("python_code", None)
    return data


def template_to_channel1_item(template: Template) -> dict:
    data = template_to_dict(template)
    metadata = template.metadata_json or data.get("metadata") or {}
    return {
        "template_id": data["template_id"],
        "template_name": data["template_name"],
        "template_name_cn": data.get("template_name_cn", ""),
        "dimension": data.get("dimension", ""),
        "complexity": data.get("complexity", ""),
        "description": data.get("description", ""),
        "dsl": data.get("dsl", ""),
        "dsl_description": data.get("dsl_description", ""),
        "parameter_space": data.get("parameter_space") or {},
        "formula_template": data.get("formula_template", ""),
        "python_function": data.get("python_function", ""),
        "python_code": data.get("python_code", ""),
        "python_module": data.get("python_module", ""),
        "examples": data.get("examples") or [],
        "status": data.get("status", ""),
        "source_channel": data.get("source_channel"),
        "execution_mode": metadata.get("execution_mode", "function"),
        "requires_external_function": metadata.get("requires_external_function", True),
        "inline_generator": metadata.get("inline_generator", ""),
    }


def template_to_pending_item(template: Template) -> dict:
    data = template_to_channel1_item(template)
    checks = template.quality_checks or {}
    data.update(
        {
            "iv": checks.get("iv", 0),
            "psi": checks.get("psi", 0),
            "coverage": checks.get("coverage", 0),
            "created_at": template.created_at.isoformat() if template.created_at else "",
            "source": template.source,
        }
    )
    return data


def list_dimensions(db: Session) -> list[TemplateDimension]:
    return (
        db.query(TemplateDimension)
        .filter(TemplateDimension.is_active.is_(True))
        .order_by(TemplateDimension.sort_order, TemplateDimension.id)
        .all()
    )


def list_templates(
    db: Session,
    status: str | None = None,
    source_channel: int | None = None,
    dimension: str | None = None,
    keyword: str | None = None,
) -> list[Template]:
    query = db.query(Template).join(TemplateDimension)
    if status:
        query = query.filter(Template.status == status)
    if source_channel:
        query = query.filter(Template.source_channel == source_channel)
    if dimension:
        query = query.filter(TemplateDimension.dimension_code == dimension)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            or_(
                Template.template_id.ilike(like),
                Template.template_name.ilike(like),
                Template.template_name_cn.ilike(like),
                Template.description.ilike(like),
                Template.dsl.ilike(like),
            )
        )
    return (
        query.order_by(TemplateDimension.sort_order, Template.template_id, Template.id)
        .all()
    )


def get_template(db: Session, template_id: str) -> Template | None:
    return db.query(Template).filter(Template.template_id == template_id).first()


def get_or_create_dimension(db: Session, dimension_code: str | None) -> TemplateDimension:
    code = (dimension_code or "derived").strip() or "derived"
    code = DIMENSION_FALLBACKS.get(code, code)
    row = (
        db.query(TemplateDimension)
        .filter(TemplateDimension.dimension_code == code)
        .first()
    )
    if row:
        return row

    max_sort = db.query(func.max(TemplateDimension.sort_order)).scalar() or 0
    row = TemplateDimension(
        dimension_code=code,
        dimension_id=None,
        dimension_name_cn=code,
        description="运行时自动补充的模板维度",
        sort_order=max_sort + 1,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(row)
    db.flush()
    return row


def next_template_id(db: Session, prefix: str = "T") -> str:
    max_id = 0
    for (template_id,) in db.query(Template.template_id).all():
        match = re.match(rf"^{re.escape(prefix)}(\d+)$", template_id or "")
        if match:
            max_id = max(max_id, int(match.group(1)))
    return f"{prefix}{max_id + 1:03d}"


def upsert_template_from_payload(
    db: Session,
    payload: dict[str, Any],
    status: str = PENDING_STATUS,
    source_channel: int = 2,
    source: str = "",
    commit: bool = True,
) -> Template:
    now = datetime.utcnow()
    template_id = payload.get("template_id") or next_template_id(db)
    dimension = get_or_create_dimension(db, payload.get("dimension"))
    row = get_template(db, template_id)
    if row is None:
        row = Template(template_id=template_id, created_at=now)
        db.add(row)

    row.template_name = payload.get("template_name") or template_id
    row.template_name_cn = payload.get("template_name_cn", "")
    row.dimension_id = dimension.id
    row.source_channel = source_channel
    row.source = source or payload.get("source", "")
    row.status = status
    row.complexity = payload.get("complexity", "")
    row.description = payload.get("description", "")
    row.dsl = payload.get("dsl", "")
    row.dsl_description = payload.get("dsl_description", "")
    row.parameter_space = payload.get("parameter_space") or {}
    row.formula_template = payload.get("formula_template", "")
    row.python_function = payload.get("python_function", "")
    row.python_code = payload.get("python_code", "")
    row.python_module = payload.get("python_module", "channel1_calculators" if status == ACTIVE_STATUS else "")
    row.examples = payload.get("examples") or []
    row.quality_checks = payload.get("quality_checks") or {
        "compile": True,
        "anti_time_travel": True,
        "dsl_syntax": True,
        "param_completeness": True,
    }
    row.metadata_json = {
        key: payload.get(key)
        for key in ["_promotion_status", "_source_file", "_promoted_from", "_promoted_at", "_promoted_round"]
        if key in payload
    }
    row.version = payload.get("version", row.version or 1)
    if status == PENDING_STATUS and row.submitted_at is None:
        row.submitted_at = now
    if status == ACTIVE_STATUS:
        row.approved_at = row.approved_at or now
        row.rejected_at = None
    if status == REJECTED_STATUS:
        row.rejected_at = row.rejected_at or now
    row.updated_at = now

    if commit:
        db.commit()
        db.refresh(row)
    else:
        db.flush()
    return row


def approve_template(
    db: Session,
    template_id: str,
    reviewer: str = "",
    reason: str = "",
) -> Template:
    row = get_template(db, template_id)
    if row is None:
        raise ValueError(f"template not found: {template_id}")
    now = datetime.utcnow()
    row.status = ACTIVE_STATUS
    row.approved_at = now
    row.rejected_at = None
    row.updated_at = now
    if not row.python_module:
        row.python_module = "channel1_calculators"
    db.add(
        TemplateReviewHistory(
            template_db_id=row.id,
            action="approved",
            reason=reason,
            reviewer=reviewer,
            source_channel=row.source_channel,
            created_at=now,
        )
    )
    db.commit()
    db.refresh(row)
    return row


def reject_template(
    db: Session,
    template_id: str,
    reason: str,
    reviewer: str = "",
) -> Template:
    if not reason:
        raise ValueError("reject reason is required")
    row = get_template(db, template_id)
    if row is None:
        raise ValueError(f"template not found: {template_id}")
    now = datetime.utcnow()
    row.status = REJECTED_STATUS
    row.rejected_at = now
    row.updated_at = now
    db.add(
        TemplateReviewHistory(
            template_db_id=row.id,
            action="rejected",
            reason=reason,
            reviewer=reviewer,
            source_channel=row.source_channel,
            created_at=now,
        )
    )
    db.add(
        TemplateRejectedMemory(
            template_db_id=row.id,
            template_id=row.template_id,
            template_name=row.template_name,
            reason=reason,
            source_channel=row.source_channel,
            created_at=now,
        )
    )
    db.commit()
    db.refresh(row)
    return row


def active_dsl_set(db: Session) -> set[str]:
    return {
        _normalize_dsl(t.dsl)
        for t in db.query(Template).filter(Template.status == ACTIVE_STATUS).all()
        if t.dsl
    }


def format_active_templates_for_prompt(db: Session) -> str:
    templates = list_templates(db, status=ACTIVE_STATUS)
    if not templates:
        return "（暂无已生效模板）"
    lines = []
    for t in templates:
        desc = (t.description or "").split("。")[0]
        lines.append(f"  - {t.template_id} {t.template_name}: DSL={t.dsl} → {desc}")
    return "\n".join(lines)


def find_template_code(template: Template) -> str:
    if _is_inline_template_record(template):
        return ""
    if template.python_code:
        return template.python_code
    module = template.python_module
    func = _function_name(template.python_function)
    if not module or not func:
        return ""
    settings = get_settings()
    possible_paths = [
        os.path.join(settings.project_root, "agents", f"{module}.py"),
        os.path.join(settings.project_root, "outputs", "feature_code", f"{module}.py"),
        os.path.join(settings.project_root, f"{module}.py"),
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return _extract_function_source(path, func)
    return ""


def append_template_python_code(template: Template) -> None:
    """Append a promoted template function into channel1_calculators.py if needed."""
    if _is_inline_template_record(template):
        return
    python_code = (template.python_code or "").strip()
    func_name = _function_name(template.python_function)
    if not python_code or not func_name:
        return

    settings = get_settings()
    calc_path = os.path.join(settings.output_dir, "feature_code", "channel1_calculators.py")
    if not os.path.exists(calc_path):
        return

    with open(calc_path, "r", encoding="utf-8") as f:
        current_code = f.read()

    changed = False
    if f"def {func_name}(" not in current_code:
        marker = "# ============================================================\n# 函数映射表\n"
        insertion = f"\n# [晋升自模板库] {template.template_id} - {template.template_name}\n"
        insertion += f"# 晋升时间: {datetime.utcnow().isoformat()}\n"
        insertion += python_code + "\n\n"
        if marker in current_code:
            current_code = current_code.replace(marker, insertion + marker)
        else:
            current_code += "\n\n" + insertion
        changed = True

    map_marker = "FUNCTION_MAP = {"
    map_line = f"    '{func_name}': {func_name},\n"
    if map_marker in current_code and f"'{func_name}':" not in current_code:
        current_code = current_code.replace(map_marker, map_marker + "\n" + map_line)
        changed = True

    if changed:
        with open(calc_path, "w", encoding="utf-8") as f:
            f.write(current_code)


def _extract_function_source(filepath: str, func_name: str) -> str:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                return ast.get_source_segment(source, node) or ""
    except Exception:
        return ""
    return ""


def _function_name(value: str | None) -> str:
    if not value:
        return ""
    match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:\(|$)", value)
    return match.group(1) if match else value.strip()


def _is_inline_template_record(template: Template) -> bool:
    metadata = template.metadata_json or {}
    if metadata.get("execution_mode") == "inline":
        return True
    if metadata.get("requires_external_function") is False:
        return True
    return (
        template.template_id == "T016"
        or (template.template_name or "") == "derived"
        or _function_name(template.python_function) == "derived_arithmetic"
        or (template.dsl or "").strip().startswith("derived(")
    )


def _normalize_dsl(dsl: str) -> str:
    normalized = dsl.strip()
    normalized = re.sub(r"==\s*['\"]?\w+['\"]?", "==*", normalized)
    normalized = re.sub(r"['\"][^'\"]*['\"]", "*", normalized)
    normalized = re.sub(r"\b\d+\b", "*", normalized)
    normalized = re.sub(r"(?<=[\s(,])[a-z_][a-z0-9_]*(?=[,)\s])", "*", normalized)
    normalized = re.sub(r"\*\s*\*", "*", normalized)
    normalized = re.sub(r"\s+", "", normalized)
    return normalized
