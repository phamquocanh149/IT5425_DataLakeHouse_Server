"""Offline restore drill with real SQLite/WAL and version-directory byte fixtures."""

import json
import sqlite3

import pytest

from scripts.backup.storage_backup import create, restore, sha256, verify
from climate_platform.modules.catalog.model import FileMetadata
from climate_platform.repositories.catalog_repository import MetadataManager


@pytest.fixture
def bundle(tmp_path):
    registry, minio, legacy = [tmp_path / name for name in ("registry", "minio", "legacy")]
    manager = MetadataManager(registry)
    manager.initialize()
    with manager.connection() as db:
        db.execute("INSERT INTO content_blobs VALUES (?,?,?)", ("a" * 64, "s3://bronze/key", 3))
        manager._insert(
            db,
            FileMetadata(
                file_id="file_1",
                source="usdm",
                source_date="2026-11-20",
                client_id="collector01",
                original_filename="raw.csv",
                stored_path="s3://bronze/key",
                size_bytes=3,
                sha256="a" * 64,
                received_at="2026-11-20T00:00:00Z",
                dataset_key="station",
                s3_bucket="bronze",
                s3_object_key="key",
                s3_version_id="v2",
            ),
        )
        db.commit()
    with sqlite3.connect(registry / "access.sqlite3") as db:
        db.execute("CREATE TABLE usage (key_id TEXT PRIMARY KEY, bytes INTEGER)")
        db.execute("INSERT INTO usage VALUES ('client:collector01',123)")
    (minio / ".minio.sys").mkdir(parents=True)
    (minio / ".minio.sys" / "format.json").write_bytes(b"test format")
    (minio / "bronze" / "v1").mkdir(parents=True)
    (minio / "bronze" / "v2").mkdir()
    (minio / "bronze" / "v1" / "part.1").write_bytes(b"old version")
    (minio / "bronze" / "v2" / "part.1").write_bytes(b"new version")
    legacy.mkdir()
    (legacy / "original.csv").write_bytes(b"legacy")
    backup = tmp_path / "bundle"
    # Keep a WAL connection open: .backup must include committed WAL data.
    with sqlite3.connect(manager.db_path) as writer:
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("UPDATE observations SET revision=2")
        writer.commit()
        create(backup, registry, minio, legacy, project="test", images=["test@sha256:fixture"])
    return backup


def test_full_bundle_restore_preserves_registry_versions_and_accounting(bundle, tmp_path):
    targets = [
        tmp_path / name for name in ("restored-registry", "restored-minio", "restored-legacy")
    ]
    manifest = restore(bundle, *targets)
    assert manifest["observations"][0]["revision"] == 2
    assert manifest["observations"][0]["s3_version_id"] == "v2"
    registry, minio, legacy = targets
    with sqlite3.connect(registry / "ingestion.sqlite3") as db:
        assert db.execute("SELECT file_id,revision FROM observations").fetchone() == ("file_1", 2)
    with sqlite3.connect(registry / "access.sqlite3") as db:
        assert db.execute("SELECT bytes FROM usage").fetchone()[0] == 123
    assert (minio / ".minio.sys" / "format.json").read_bytes() == b"test format"
    assert (minio / "bronze" / "v1" / "part.1").read_bytes() == b"old version"
    assert (minio / "bronze" / "v2" / "part.1").read_bytes() == b"new version"
    assert (legacy / "original.csv").read_bytes() == b"legacy"
    with pytest.raises(ValueError, match="empty NEW"):
        restore(bundle, *targets)


@pytest.mark.parametrize("artifact", ["minio-data.tar.gz", "registry.tar.gz", "manifest.json"])
def test_corrupt_bundle_rejected_before_restore_writes(bundle, tmp_path, artifact):
    with (bundle / artifact).open("ab") as stream:
        stream.write(b"corruption")
    targets = [tmp_path / name for name in ("new-registry", "new-minio", "new-legacy")]
    with pytest.raises(ValueError, match="checksum"):
        restore(bundle, *targets)
    assert not any(path.exists() for path in targets)


def test_incomplete_bundle_cannot_be_accepted(bundle):
    path = bundle / "manifest.json"
    manifest = json.loads(path.read_text())
    del manifest["artifacts"]["minio"]
    path.write_text(json.dumps(manifest))
    (bundle / "manifest.sha256").write_text(sha256(path))
    with pytest.raises(ValueError, match="Incomplete"):
        verify(bundle)
