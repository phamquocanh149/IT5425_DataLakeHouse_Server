"""Offline-safe migration and conservative recovery; never delete raw data."""

import json
import shutil
import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, insert, or_, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from climate_platform.common.hashing import file_hash
from climate_platform.config import settings
from climate_platform.entity.registry import ContentBlob, Observation, RecoveryReport
from climate_platform.entity.view import FileMetadata
from climate_platform.repositories.catalog_repository import metadata_manager


def migrate_json(manager=metadata_manager):
    files = sorted(manager.metadata_dir.glob("*.json"))
    backup = (
        manager.metadata_dir
        / "backups"
        / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8])
    )
    backup.mkdir(parents=True)
    for path in files:
        shutil.copy2(path, backup / path.name)
    report = {"backup": str(backup), "imported": [], "skipped": [], "errors": []}
    candidates = []
    for path in files:
        try:
            record = FileMetadata(**json.loads(path.read_text(encoding="utf-8")))
            from climate_platform.modules.ingestion.validation import (
                validate_source,
                validate_source_date,
            )

            validate_source(record.source)
            validate_source_date(record.source_date)
            raw = manager.resolve_raw(record.stored_path)
            if not raw.is_file():
                raise ValueError("Bronze file missing")
            if raw.stat().st_size != record.size_bytes or file_hash(raw) != record.sha256:
                raise ValueError("Bronze checksum or size mismatch")
            if record.status != "VERIFIED":
                raise ValueError("Legacy record is not VERIFIED; manual review required")
            record.dataset_key = record.dataset_key or record.original_filename
            record.stored_path = raw.relative_to(settings.BASE_DIR).as_posix()
            candidates.append((path, record))
        except Exception as exc:
            report["errors"].append(
                {
                    "file": path.name,
                    "error": str(exc) if isinstance(exc, ValueError) else type(exc).__name__,
                }
            )
    for path, record in sorted(candidates, key=lambda item: (item[1].received_at, item[1].file_id)):
        try:
            with manager.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                identity = (record.source, record.source_date, record.dataset_key)
                existing = (
                    db.execute(
                        select(Observation).where(
                            or_(
                                Observation.file_id == record.file_id,
                                and_(
                                    Observation.source == identity[0],
                                    Observation.source_date == identity[1],
                                    Observation.dataset_key == identity[2],
                                    Observation.sha256 == record.sha256,
                                ),
                            )
                        )
                    )
                    .mappings()
                    .first()
                )
                if existing:
                    if (
                        existing["source"],
                        existing["source_date"],
                        existing["dataset_key"],
                        existing["sha256"],
                        existing["client_id"],
                    ) != (*identity, record.sha256, record.client_id):
                        raise ValueError("Conflicting existing file_id")
                    report["skipped"].append(path.name)
                    continue
                current = (
                    db.execute(
                        select(Observation).where(
                            Observation.source == identity[0],
                            Observation.source_date == identity[1],
                            Observation.dataset_key == identity[2],
                            Observation.is_current == 1,
                        )
                    )
                    .mappings()
                    .first()
                )
                record.revision = current["revision"] + 1 if current else 1
                record.previous_file_id = current["file_id"] if current else None
                record.is_current = True
                db.execute(
                    sqlite_insert(ContentBlob)
                    .values(
                        sha256=record.sha256,
                        stored_path=record.stored_path,
                        size_bytes=record.size_bytes,
                    )
                    .on_conflict_do_nothing(index_elements=[ContentBlob.sha256])
                )
                db.execute(
                    update(Observation)
                    .where(
                        Observation.source == identity[0],
                        Observation.source_date == identity[1],
                        Observation.dataset_key == identity[2],
                    )
                    .values(is_current=0)
                )
                manager._insert(db, record)
                db.commit()
                report["imported"].append(path.name)
        except Exception as exc:
            report["errors"].append({"file": path.name, "error": type(exc).__name__})
    (backup / "migration_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def reconcile(manager=metadata_manager, *, checksum=False, repair=False):
    if settings.STORAGE_BACKEND == "s3":
        from climate_platform.modules.catalog.s3_maintenance import reconcile_s3

        return reconcile_s3(manager, repair=repair)
    report = {
        "temporary_files": [],
        "orphan_files": [],
        "missing": [],
        "corrupt": [],
        "unsafe_paths": [],
        "repaired_status": [],
    }
    with manager.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        known = set()
        for row in db.execute(select(Observation)).mappings().all():
            try:
                path = manager.resolve_raw(row["stored_path"])
            except ValueError:
                report["unsafe_paths"].append(row["file_id"])
                continue
            known.add(path)
            state = "VERIFIED"
            if not path.is_file():
                state = "MISSING"
                report["missing"].append(row["file_id"])
            elif path.stat().st_size != row["size_bytes"] or (
                (checksum or repair) and file_hash(path) != row["sha256"]
            ):
                state = "CORRUPT"
                report["corrupt"].append(row["file_id"])
            if repair and state != row["status"]:
                db.execute(
                    update(Observation)
                    .where(Observation.file_id == row["file_id"])
                    .values(
                        status=state,
                        error_message=None if state == "VERIFIED" else "Reconciliation: " + state,
                    )
                )
                report["repaired_status"].append(row["file_id"])
        report["orphan_files"] = [
            p.relative_to(settings.BASE_DIR).as_posix()
            for p in settings.bronze_path.rglob("*")
            if p.is_file() and p.name != ".gitkeep" and p.resolve() not in known
        ]
        report["temporary_files"] = [
            p.name for p in settings.temp_path.glob("*") if p.is_file() and p.name != ".gitkeep"
        ]
        db.execute(
            insert(RecoveryReport).values(
                report_id=uuid.uuid4().hex,
                created_at=datetime.now(timezone.utc).isoformat(),
                report_json=json.dumps(report),
            )
        )
        db.commit()
    return report
