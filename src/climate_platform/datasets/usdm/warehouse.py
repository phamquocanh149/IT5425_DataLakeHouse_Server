"""USDM warehouse access (ORM).

One job: read/record the build/attempt/gold-cell rows in ``warehouse.sqlite3`` through the
SQLAlchemy entities. Transaction control (``BEGIN IMMEDIATE``) is the only raw SQL.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

from sqlalchemy import insert, select

from climate_platform.entity.warehouse import Attempt, Build, GoldCell
from climate_platform.repositories.warehouse_repository import db as warehouse_db
from climate_platform.repositories.warehouse_repository import initialize_catalog

__all__ = ["initialize_catalog", "existing_manifest", "record_attempt", "commit_build"]


def _now():
    return datetime.now(timezone.utc).isoformat()


def existing_manifest(catalog, build):
    with warehouse_db(catalog) as db:
        row = db.execute(select(Build.manifest).where(Build.build_id == build)).mappings().first()
    return json.loads(row["manifest"]) if row else None


def record_attempt(catalog, day, status, detail):
    with warehouse_db(catalog) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            insert(Attempt).values(
                source_date=day,
                status=status,
                detail=detail,
                created_at=_now(),
            )
        )


def commit_build(catalog, build, record, day, sha, manifest, gold_csv):
    """Commit one build's metadata and Gold cells in a single atomic transaction."""
    with warehouse_db(catalog) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            insert(Build).values(
                build_id=build,
                file_id=record.file_id,
                source_date=day,
                revision=record.revision,
                raw_sha256=sha,
                manifest=json.dumps(manifest, sort_keys=True),
                completed_at=_now(),
            )
        )
        with gold_csv.open(encoding="utf-8", newline="") as stream:
            cells = [
                {
                    "build_id": build,
                    "time": row["time"],
                    "grid": row["grid"],
                    "lon": float(row["lon"]),
                    "lat": float(row["lat"]),
                    "drought": row["drought"],
                }
                for row in csv.DictReader(stream)
            ]
        if cells:
            db.execute(insert(GoldCell), cells)
