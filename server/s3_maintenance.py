"""Conservative S3 migration/reconciliation. Never delete objects or legacy files."""

import sqlite3
from contextlib import closing
import uuid
from datetime import datetime, timezone

from botocore.exceptions import ClientError

from .metadata import file_hash, metadata_manager
from .storage import S3Storage, object_key
from .config import settings


def migrate_bronze(manager=metadata_manager, *, dry_run=True):
    storage = S3Storage()
    report = {
        "dry_run": dry_run,
        "backup": None,
        "files": [],
        "migrated": [],
        "skipped": [],
        "errors": [],
    }
    with manager.connection() as db:
        if not dry_run:
            directory = manager.metadata_dir / "backups" / ("s3-" + uuid.uuid4().hex)
            directory.mkdir(parents=True)
            backup = directory / "ingestion.sqlite3"
            with closing(sqlite3.connect(backup)) as target:
                db.backup(target)
            report["backup"] = str(backup)
        rows = db.execute("SELECT * FROM observations ORDER BY received_at, file_id").fetchall()
        updates = []
        # Offline maintenance: network I/O precedes the short guarded commit.
        for row in rows:
            try:
                if row["s3_object_key"]:
                    storage.verify(
                        row["s3_object_key"], row["sha256"], row["size_bytes"], row["s3_bucket"]
                    )
                    report["skipped"].append(row["file_id"])
                    continue
                path = manager.resolve_raw(row["stored_path"])
                if (
                    row["status"] != "VERIFIED"
                    or path.stat().st_size != row["size_bytes"]
                    or file_hash(path) != row["sha256"]
                ):
                    raise ValueError("Local content not verified")
                key = object_key(
                    row["source"],
                    row["source_date"],
                    row["dataset_key"],
                    row["revision"],
                    row["sha256"],
                    row["original_filename"],
                )
                report["files"].append(
                    {
                        "file_id": row["file_id"],
                        "local": row["stored_path"],
                        "bucket": storage.bucket,
                        "key": key,
                        "sha256": row["sha256"],
                    }
                )
                if not dry_run:
                    version = storage.publish(path, key, row["sha256"], row["size_bytes"])
                    # Preserve stored_path and content_blobs as rollback references for legacy data.
                    updates.append((storage.bucket, key, version, row["file_id"]))
            except Exception as exc:
                report["errors"].append({"file_id": row["file_id"], "error": type(exc).__name__})
        if updates:
            db.execute("BEGIN IMMEDIATE")
            latest = db.execute(
                "SELECT * FROM observations ORDER BY received_at, file_id"
            ).fetchall()
            if [dict(r) for r in latest] != [dict(r) for r in rows]:
                raise RuntimeError("Registry changed during migration; pause writers and retry")
            db.executemany(
                "UPDATE observations SET s3_bucket=?, s3_object_key=?, s3_version_id=? WHERE file_id=?",
                updates,
            )
            db.commit()
            report["migrated"] = [item[3] for item in updates]
    return report


def reconcile_s3(manager=metadata_manager, *, repair=False):
    storage = S3Storage()
    report = {
        "missing": [],
        "corrupt": [],
        "unmigrated": [],
        "orphan_objects": [],
        "repaired_status": [],
    }
    # Failure to list/read due to network or access errors aborts; never mark data missing on outage.
    with manager.connection() as db:
        rows = db.execute("SELECT * FROM observations ORDER BY file_id").fetchall()
        updates = []
        known = set()
        for row in rows:
            if not row["s3_object_key"]:
                report["unmigrated"].append(row["file_id"])
                continue
            known.add((row["s3_bucket"], row["s3_object_key"]))
            state = "VERIFIED"
            try:
                expected = object_key(
                    row["source"],
                    row["source_date"],
                    row["dataset_key"],
                    row["revision"],
                    row["sha256"],
                    row["original_filename"],
                )
                if row["s3_object_key"] != expected or row["s3_bucket"] != storage.bucket:
                    raise ValueError("Unexpected mapping")
                storage.verify(
                    row["s3_object_key"], row["sha256"], row["size_bytes"], row["s3_bucket"]
                )
            except ClientError as exc:
                if exc.response["Error"]["Code"] not in ("NoSuchKey", "404"):
                    raise
                state = "MISSING"
                report["missing"].append(row["file_id"])
            except ValueError:
                state = "CORRUPT"
                report["corrupt"].append(row["file_id"])
            if repair and state != row["status"]:
                updates.append(
                    (
                        state,
                        None if state == "VERIFIED" else "S3 reconciliation: " + state,
                        row["file_id"],
                    )
                )
                report["repaired_status"].append(row["file_id"])
        report["orphan_objects"] = [
            obj["Key"] for obj in storage.objects() if (storage.bucket, obj["Key"]) not in known
        ]
        import json

        db.execute("BEGIN IMMEDIATE")
        latest = db.execute("SELECT * FROM observations ORDER BY file_id").fetchall()
        if [dict(r) for r in latest] != [dict(r) for r in rows]:
            raise RuntimeError("Registry changed during reconciliation; pause writers and retry")
        db.executemany("UPDATE observations SET status=?,error_message=? WHERE file_id=?", updates)
        db.execute(
            "INSERT INTO recovery_reports VALUES (?,?,?)",
            (uuid.uuid4().hex, datetime.now(timezone.utc).isoformat(), json.dumps(report)),
        )
        db.commit()
    return report


def local_inventory(manager=metadata_manager):
    return {
        "bronze_files": [
            str(p.relative_to(settings.BASE_DIR))
            for p in settings.bronze_path.rglob("*")
            if p.is_file() and p.name != ".gitkeep"
        ],
        "legacy_metadata": [p.name for p in manager.metadata_dir.glob("*.json")],
    }
