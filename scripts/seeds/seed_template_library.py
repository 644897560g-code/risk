"""Seed template dimensions and active channel1 templates from JSON."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.models.template import Template, TemplateDimension
from backend.services.template_library import (
    PENDING_STATUS,
    find_template_code,
    upsert_template_from_payload,
)


DEFAULT_TEMPLATE_SOURCE = Path("outputs/feature_templates/channel1_templates.json")
DEFAULT_PENDING_TEMPLATE_SOURCE = Path("scripts/seeds/fixtures/channel2_pending.seed.json")


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _source_channel(value: Any) -> int:
    if value in ("channel1", "bootstrap", "", None):
        return 1
    if value == "channel2":
        return 2
    if value == "knowledge":
        return 3
    return 1


def _metadata_from_template(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item.get(key)
        for key in ["_promoted_from", "_promoted_at", "_promoted_round"]
        if key in item
    }


def _is_inline_template(item: dict[str, Any]) -> bool:
    """Templates expanded by the generator instead of imported as functions."""
    template_id = item.get("template_id", "")
    template_name = item.get("template_name", "")
    python_function = item.get("python_function", "")
    dsl = item.get("dsl", "")
    return (
        template_id == "T016"
        or template_name == "derived"
        or python_function == "derived_arithmetic"
        or dsl.strip().startswith("derived(")
    )


def seed_template_library(
    db: Session,
    source: Path = DEFAULT_TEMPLATE_SOURCE,
    dry_run: bool = False,
) -> dict[str, int]:
    """Seed template dimensions and active templates.

    The operation is idempotent. Existing rows are updated by stable keys:
    - dimensions: dimension_code
    - templates: template_id
    """
    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(f"template source not found: {source}")

    with source.open("r", encoding="utf-8") as f:
        data = json.load(f)

    dimensions = data.get("dimensions", [])
    templates = data.get("templates", [])
    now = datetime.utcnow()

    stats = {
        "dimensions_inserted": 0,
        "dimensions_updated": 0,
        "templates_inserted": 0,
        "templates_updated": 0,
        "templates_skipped": 0,
    }

    dimension_by_code: dict[str, TemplateDimension] = {}
    for index, item in enumerate(dimensions, start=1):
        code = item.get("dimension_name")
        if not code:
            continue

        row = (
            db.query(TemplateDimension)
            .filter(TemplateDimension.dimension_code == code)
            .first()
        )
        if row is None:
            row = TemplateDimension(
                dimension_code=code,
                created_at=now,
            )
            db.add(row)
            stats["dimensions_inserted"] += 1
        else:
            stats["dimensions_updated"] += 1

        row.dimension_id = item.get("dimension_id")
        row.dimension_name_cn = item.get("dimension_name_cn", "")
        row.description = item.get("description", "")
        row.sort_order = index
        row.is_active = True
        row.updated_at = now
        dimension_by_code[code] = row

    if not dry_run:
        db.flush()

    for item in templates:
        template_id = item.get("template_id")
        dimension_code = item.get("dimension")
        if not template_id or not dimension_code:
            stats["templates_skipped"] += 1
            continue

        dimension = dimension_by_code.get(dimension_code)
        if dimension is None:
            dimension = (
                db.query(TemplateDimension)
                .filter(TemplateDimension.dimension_code == dimension_code)
                .first()
            )
        if dimension is None:
            stats["templates_skipped"] += 1
            continue

        row = db.query(Template).filter(Template.template_id == template_id).first()
        promoted_from = item.get("_promoted_from", "bootstrap")
        promoted_at = _parse_dt(item.get("_promoted_at")) or now
        if row is None:
            row = Template(
                template_id=template_id,
                created_at=now,
            )
            db.add(row)
            stats["templates_inserted"] += 1
        else:
            stats["templates_updated"] += 1

        row.template_name = item.get("template_name", "")
        row.template_name_cn = item.get("template_name_cn", "")
        row.dimension_id = dimension.id
        row.source_channel = _source_channel(promoted_from)
        row.source = promoted_from or "bootstrap"
        row.status = "active"
        row.complexity = item.get("complexity", "")
        row.description = item.get("description", "")
        row.dsl = item.get("dsl", "")
        row.dsl_description = item.get("dsl_description", "")
        row.parameter_space = item.get("parameter_space") or {}
        row.formula_template = item.get("formula_template", "")
        inline_template = _is_inline_template(item)
        if inline_template:
            row.python_function = ""
            row.python_module = ""
            row.python_code = ""
        else:
            row.python_function = item.get("python_function", "")
            row.python_module = item.get("python_module", "")
            row.python_code = item.get("python_code") or find_template_code(row)
        row.examples = item.get("examples") or []
        row.quality_checks = {
            "compile": True,
            "anti_time_travel": True,
            "dsl_syntax": True,
            "param_completeness": True,
            "source": "bootstrap_seed",
        }
        metadata = _metadata_from_template(item)
        if inline_template:
            metadata.update(
                {
                    "execution_mode": "inline",
                    "requires_external_function": False,
                    "inline_generator": "agents.feature_mass_producer._compose_T016",
                    "inline_reason": "T016 derived features are pure arithmetic over previously calculated primary features.",
                }
            )
            row.quality_checks["execution_mode"] = "inline"
            row.quality_checks["requires_external_function"] = False
        row.metadata_json = metadata
        row.version = 1
        row.submitted_at = promoted_at
        row.approved_at = promoted_at
        row.rejected_at = None
        row.updated_at = now

    if dry_run:
        db.rollback()
    else:
        db.commit()

    return stats


def seed_pending_templates(
    db: Session,
    source: Path = DEFAULT_PENDING_TEMPLATE_SOURCE,
    dry_run: bool = False,
) -> dict[str, int]:
    """Seed historical channel2 pending templates.

    This imports old local pending JSON once into PostgreSQL. It is idempotent:
    - active templates are never demoted back to pending
    - pending/rejected rows with the same template_id are updated
    """
    source = Path(source)
    stats = {
        "pending_inserted": 0,
        "pending_updated": 0,
        "pending_skipped": 0,
        "pending_source_missing": 0,
    }
    if not source.exists():
        stats["pending_source_missing"] = 1
        return stats

    with source.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        templates = data.get("items", data.get("templates", []))
    elif isinstance(data, list):
        templates = data
    else:
        templates = []

    for item in templates:
        if not isinstance(item, dict):
            stats["pending_skipped"] += 1
            continue

        template_id = item.get("template_id")
        existing = (
            db.query(Template)
            .filter(Template.template_id == template_id)
            .first()
            if template_id
            else None
        )
        if existing and existing.status == "active":
            stats["pending_skipped"] += 1
            continue

        row = upsert_template_from_payload(
            db,
            item,
            status=PENDING_STATUS,
            source_channel=2,
            source=item.get("source", "channel2_pending_seed"),
            commit=False,
        )
        if existing:
            stats["pending_updated"] += 1
        else:
            stats["pending_inserted"] += 1
        row.metadata_json = {
            **(row.metadata_json or {}),
            "seed_source": str(source),
            "_promotion_status": item.get("_promotion_status", "pending"),
        }

    if dry_run:
        db.rollback()
    else:
        db.commit()

    return stats
