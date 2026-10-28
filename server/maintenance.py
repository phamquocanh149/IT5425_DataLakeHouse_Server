"""Offline-safe migration and conservative recovery; never delete raw data."""
import json
import shutil
import uuid
from datetime import datetime, timezone

from .config import settings
from .metadata import FileMetadata, file_hash, metadata_manager


def migrate_json(manager=metadata_manager):
    files = sorted(manager.metadata_dir.glob("*.json"))
    backup = manager.metadata_dir / "backups" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8])
    backup.mkdir(parents=True)
    for path in files:
        shutil.copy2(path, backup / path.name)
    report = {"backup": str(backup), "imported": [], "skipped": [], "errors": []}
    candidates = []
    for path in files:
        try:
            record = FileMetadata(**json.loads(path.read_text(encoding="utf-8")))
            from .ingestion import validate_source, validate_source_date
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
            report["errors"].append({"file": path.name, "error": str(exc) if isinstance(exc, ValueError) else type(exc).__name__})
    for path, record in sorted(candidates, key=lambda item: (item[1].received_at, item[1].file_id)):
        try:
            with manager.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                identity = (record.source, record.source_date, record.dataset_key)
                existing = db.execute("SELECT * FROM observations WHERE file_id=? OR (source=? AND source_date=? AND dataset_key=? AND sha256=?)",
                                      (record.file_id, *identity, record.sha256)).fetchone()
                if existing:
                    if (existing["source"], existing["source_date"], existing["dataset_key"], existing["sha256"], existing["client_id"]) != (*identity, record.sha256, record.client_id):
                        raise ValueError("Conflicting existing file_id")
                    report["skipped"].append(path.name)
                    continue
                current = db.execute("SELECT * FROM observations WHERE source=? AND source_date=? AND dataset_key=? AND is_current=1", identity).fetchone()
                record.revision = current["revision"] + 1 if current else 1
                record.previous_file_id = current["file_id"] if current else None
                record.is_current = True
                db.execute("INSERT OR IGNORE INTO content_blobs VALUES (?,?,?)", (record.sha256, record.stored_path, record.size_bytes))
                db.execute("UPDATE observations SET is_current=0 WHERE source=? AND source_date=? AND dataset_key=?", identity)
                manager._insert(db, record)
                db.commit()
                report["imported"].append(path.name)
        except Exception as exc:
            report["errors"].append({"file": path.name, "error": type(exc).__name__})
    (backup / "migration_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def reconcile(manager=metadata_manager, *, checksum=False, repair=False):
    report = {"temporary_files": [], "orphan_files": [], "missing": [], "corrupt": [], "unsafe_paths": [], "repaired_status": []}
    with manager.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        known = set()
        for row in db.execute("SELECT * FROM observations").fetchall():
            try:
                path = manager.resolve_raw(row["stored_path"])
            except ValueError:
                report["unsafe_paths"].append(row["file_id"])
                continue
            known.add(path)
            state = "VERIFIED"
            if not path.is_file():
                state = "MISSING"; report["missing"].append(row["file_id"])
            elif path.stat().st_size != row["size_bytes"] or ((checksum or repair) and file_hash(path) != row["sha256"]):
                state = "CORRUPT"; report["corrupt"].append(row["file_id"])
            if repair and state != row["status"]:
                db.execute("UPDATE observations SET status=?, error_message=? WHERE file_id=?",
                           (state, None if state == "VERIFIED" else "Reconciliation: " + state, row["file_id"]))
                report["repaired_status"].append(row["file_id"])
        report["orphan_files"] = [p.relative_to(settings.BASE_DIR).as_posix() for p in settings.bronze_path.rglob("*")
                                  if p.is_file() and p.name != ".gitkeep" and p.resolve() not in known]
        report["temporary_files"] = [p.name for p in settings.temp_path.glob("*") if p.is_file() and p.name != ".gitkeep"]
        db.execute("INSERT INTO recovery_reports VALUES (?,?,?)", (uuid.uuid4().hex, datetime.now(timezone.utc).isoformat(), json.dumps(report)))
        db.commit()
    return report
