"""Real S3 fault/migration checks. Only run in the isolated compose_smoke project."""

import asyncio
import hashlib
import io
import sqlite3
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from fastapi import UploadFile  # noqa: E402
from climate_platform.repositories.catalog_repository import metadata_manager  # noqa: E402
from climate_platform.modules.catalog.s3_maintenance import migrate_bronze, reconcile_s3  # noqa: E402
from climate_platform.config import settings  # noqa: E402
from climate_platform.s3.minio_repository import S3Storage  # noqa: E402
from climate_platform.modules.ingestion.service import process_file_upload  # noqa: E402
from botocore.exceptions import ClientError  # noqa: E402


def send(content=b"fault-data", key="fault-check"):
    return asyncio.run(
        process_file_upload(
            UploadFile(filename="fault.csv", file=io.BytesIO(content)),
            "usgs",
            "2021-06-22",
            "collector01",
            key,
        )
    )


def main():
    assert settings.S3_BUCKET_BRONZE.startswith("climate-smoke-")
    storage = S3Storage()
    with tempfile.TemporaryDirectory() as directory:
        settings.BASE_DIR = Path(directory)
        metadata_manager.metadata_dir = Path(directory) / "metadata"
        settings.ensure_directories()
        metadata_manager.initialize()
        # A real SQLite commit failure leaves a verified S3 object, but no observation.
        from climate_platform.repositories import database as db_module

        real_commit = db_module.DatabaseConnection.commit

        def commit(self):
            if "ingestion.sqlite3" in str(self._connection.engine.url):
                raise sqlite3.OperationalError("injected commit failure")
            return real_commit(self)

        with patch.object(db_module.DatabaseConnection, "commit", commit):
            try:
                send()
                raise AssertionError("Commit failure expected")
            except sqlite3.OperationalError:
                pass
        assert not metadata_manager.list_all()
        orphans = reconcile_s3()["orphan_objects"]
        record = send().metadata
        assert record.s3_object_key in orphans
        assert record.s3_object_key not in reconcile_s3()["orphan_objects"]
        assert send().status == "DUPLICATE"
        try:
            storage.publish(
                Path(directory) / "missing", record.s3_object_key, record.sha256, record.size_bytes
            )
        except FileNotFoundError:
            pass
        # Conditional publisher cannot overwrite existing raw, even with different bytes.
        wrong = Path(directory) / "wrong.csv"
        wrong.write_bytes(b"different")
        try:
            storage.publish(
                wrong, record.s3_object_key, hashlib.sha256(b"different").hexdigest(), 9
            )
            raise AssertionError("Existing raw must not be overwritten")
        except ValueError:
            pass
        storage.verify(record.s3_object_key, record.sha256, record.size_bytes)
        # Untrusted metadata/ETag cannot hide corrupt bytes: only download hashing verifies.
        storage.client.put_object(
            Bucket=storage.bucket,
            Key=record.s3_object_key,
            Body=b"bad--bytes",
            Metadata={"sha256": record.sha256},
        )
        assert reconcile_s3(repair=True)["corrupt"] == [record.file_id]
        storage.client.put_object(
            Bucket=storage.bucket, Key=record.s3_object_key, Body=b"fault-data"
        )
        assert reconcile_s3(repair=True)["repaired_status"] == [record.file_id]
        with ThreadPoolExecutor(max_workers=4) as pool:
            statuses = list(
                pool.map(lambda _: send(b"parallel", "parallel-check").status, range(4))
            )
        assert sorted(statuses) == ["DUPLICATE"] * 3 + ["VERIFIED"]
        # No delete/admin/Silver permissions for ingestion credentials.
        for action in (
            lambda: storage.client.delete_object(Bucket=storage.bucket, Key=record.s3_object_key),
            lambda: storage.client.list_objects_v2(
                Bucket=storage.bucket.replace("-bronze", "-silver")
            ),
        ):
            try:
                action()
                raise AssertionError("Least privilege check failed")
            except ClientError as exc:
                assert exc.response["Error"]["Code"] == "AccessDenied"
        with metadata_manager.connection() as db:
            db.execute(
                "UPDATE observations SET s3_object_key='bad-key' WHERE file_id=?", (record.file_id,)
            )
            db.commit()
        assert reconcile_s3()["corrupt"] == [record.file_id]
        with metadata_manager.connection() as db:
            db.execute(
                "UPDATE observations SET s3_object_key=? WHERE file_id=?",
                (record.s3_object_key, record.file_id),
            )
            db.commit()
        settings.STORAGE_BACKEND = "local"
        legacy = send(b"legacy-content", "legacy-check").metadata
        local = settings.BASE_DIR / legacy.stored_path
        settings.STORAGE_BACKEND = "s3"
        dry = migrate_bronze(dry_run=True)
        assert not dry["errors"] and not dry["migrated"] and len(dry["files"]) == 1
        result = migrate_bronze(dry_run=False)
        assert not result["errors"] and result["migrated"] == [legacy.file_id]
        assert Path(result["backup"]).is_file() and local.read_bytes() == b"legacy-content"
        assert not migrate_bronze(dry_run=False)["migrated"]
        assert send(b"legacy-content", "legacy-check").status == "DUPLICATE"
    print(
        "PASS: real S3 commit-failure/orphan adoption, immutable PUT, least privilege, mapping reconciliation, migration backup/dry-run/idempotency"
    )


if __name__ == "__main__":
    main()
