#!/usr/bin/env python
"""Initialize platform seed data after Alembic migrations.

Run from repository root:

    DATABASE_URL=postgresql+psycopg://... python scripts/init_project_data.py
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.database import SessionLocal  # noqa: E402
from scripts.seeds.seed_template_library import (  # noqa: E402
    seed_pending_templates,
    seed_template_library,
)


def _require_database_url() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required before running project initialization")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize RiskForge platform seed data")
    parser.add_argument(
        "--template-source",
        default="outputs/feature_templates/channel1_templates.json",
        help="Path to channel1 template JSON source",
    )
    parser.add_argument(
        "--pending-template-source",
        default="scripts/seeds/fixtures/channel2_pending.seed.json",
        help="Path to historical channel2 pending template JSON seed source",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run seed logic and rollback changes",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    _require_database_url()

    db = SessionLocal()
    try:
        template_stats = seed_template_library(
            db=db,
            source=Path(args.template_source),
            dry_run=args.dry_run,
        )
        pending_stats = seed_pending_templates(
            db=db,
            source=Path(args.pending_template_source),
            dry_run=args.dry_run,
        )
    finally:
        db.close()

    prefix = "[dry-run] " if args.dry_run else ""
    print(prefix + "template_library:")
    for key, value in template_stats.items():
        print(f"  {key}: {value}")
    print(prefix + "pending_templates:")
    for key, value in pending_stats.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
