import asyncio
import io
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile

from server.config import Settings, settings
from server.ingestion import process_file_upload
from server.metadata import metadata_manager, file_hash
from server.maintenance import migrate_json, reconcile
from tests.test_server import setup_test_environment, client


def send(client, source="usdm", day="2021-06-22", content=b"mock climate data", key="station1", api_key="test-only-collector", **extra):
    return client.post("/upload", headers={"X-API-Key": api_key},
        data={"source": source, "source_date": day, "dataset_key": key, **extra},
        files={"file": ("sample.csv", content, "text/csv")})


def test_auth_and_all_sources(client, monkeypatch):
    for source in ["usdm", "noaa", "usgs", "nldas"]:
        response = send(client, source, client_id="admin")
        assert response.status_code == 200
        assert response.json()["metadata"]["client_id"] == "collector01"
    assert send(client, api_key="bad").status_code == 401
    assert send(client, api_key="test-only-admin").status_code == 403
    monkeypatch.setattr(settings, "COLLECTOR_SOURCES", {"usdm"})
    assert send(client, "noaa").status_code == 403
    assert client.get("/uploads?source=noaa", headers={"X-API-Key": "test-only-collector"}).status_code == 403


def test_metadata_visibility(client):
    send(client)
    send(client, key="legacy", api_key="test-only-client01")
    collector = client.get("/uploads", headers={"X-API-Key": "test-only-collector"}).json()
    admin = client.get("/uploads", headers={"X-API-Key": "test-only-admin"}).json()
    assert len(collector) == 1 and len(admin) == 2
    assert send(client, api_key="test-only-client01").status_code == 403


def test_key_validation(monkeypatch):
    with pytest.raises(ValueError, match="distinct"):
        Settings(_env_file=None, COLLECTOR_API_KEY="same", ADMIN_API_KEY="same", DEBUG=False)
    config = Settings(_env_file=None, COLLECTOR_API_KEY="collector", ADMIN_API_KEY="admin", CLIENT01_API_KEY="legacy", DEBUG=False)
    assert "legacy" not in config.api_keys


def test_observations_revisions_and_blobs(client):
    first = send(client).json()["metadata"]
    assert send(client).json()["status"] == "DUPLICATE"
    day2 = send(client, day="2021-06-23").json()["metadata"]
    other_source = send(client, source="noaa").json()["metadata"]
    assert len({first["file_id"], day2["file_id"], other_source["file_id"]}) == 3
    assert first["stored_path"] == day2["stored_path"] == other_source["stored_path"]
    revision = send(client, content=b"changed mock data").json()["metadata"]
    assert revision["revision"] == 2 and revision["previous_file_id"] == first["file_id"]
    assert metadata_manager.get_by_file_id(first["file_id"]).is_current is False
    old_retry = send(client).json()["metadata"]
    assert old_retry["file_id"] == first["file_id"] and not old_retry["is_current"]
    assert metadata_manager.get_by_file_id(revision["file_id"]).is_current
    with metadata_manager.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM content_blobs").fetchone()[0] == 2
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            metadata_manager._insert(db, metadata_manager.get_by_file_id(first["file_id"]))


def test_concurrent_identical_requests(setup_test_environment):
    def upload(_):
        return asyncio.run(process_file_upload(UploadFile(filename="same.csv", file=io.BytesIO(b"same")), "usgs", "2021-06-22", "collector01", "same"))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(upload, range(4)))
    assert sorted(r.status for r in results) == ["DUPLICATE"] * 3 + ["VERIFIED"]
    assert len(metadata_manager.list_all()) == 1


def test_registry_failure_and_orphan_recovery(client, monkeypatch):
    original = metadata_manager._insert
    def fail(*args):
        raise sqlite3.OperationalError("simulated DB failure")
    monkeypatch.setattr(metadata_manager, "_insert", fail)
    with pytest.raises(sqlite3.OperationalError):
        send(client)
    assert not metadata_manager.list_all()
    report = reconcile(checksum=True)
    assert len(report["orphan_files"]) == 1
    raw = settings.BASE_DIR / report["orphan_files"][0]
    before = raw.read_bytes()
    monkeypatch.setattr(metadata_manager, "_insert", original)
    assert send(client).json()["status"] == "VERIFIED"
    assert raw.read_bytes() == before
    assert not reconcile()["orphan_files"]


def test_file_publish_failure_never_verifies(client, monkeypatch):
    import server.metadata as registry
    def fail(*args):
        raise OSError("simulated disk failure")
    monkeypatch.setattr(registry.os, "replace", fail)
    with pytest.raises(OSError):
        send(client)
    assert metadata_manager.list_all() == []
    assert list(settings.temp_path.glob("*.tmp")) == []


def test_registry_commit_failure_rolls_back(client, monkeypatch):
    real_connect = sqlite3.connect
    class FailingCommit(sqlite3.Connection):
        def commit(self):
            raise sqlite3.OperationalError("simulated commit failure")
    def connect(*args, **kwargs):
        return real_connect(*args, **kwargs, factory=FailingCommit)
    with monkeypatch.context() as patch:
        patch.setattr(sqlite3, "connect", connect)
        with pytest.raises(sqlite3.OperationalError):
            send(client)
    assert metadata_manager.list_all() == []
    assert reconcile()["orphan_files"]
    assert send(client).json()["status"] == "VERIFIED"


def test_reconcile_missing_corrupt_and_temporary(client):
    meta = send(client).json()["metadata"]
    path = settings.BASE_DIR / meta["stored_path"]
    original = path.read_bytes()
    path.write_bytes(b"corrupt")
    (settings.temp_path / "old.tmp").write_bytes(b"interrupted")
    report = reconcile(checksum=True, repair=True)
    assert report["corrupt"] == [meta["file_id"]] and report["temporary_files"] == ["old.tmp"]
    assert send(client).status_code == 503
    path.unlink()
    assert reconcile(repair=True)["missing"] == [meta["file_id"]]
    path.write_bytes(original)
    assert reconcile(repair=True)["repaired_status"] == [meta["file_id"]]
    assert send(client).json()["status"] == "DUPLICATE"


def test_migration_backup_idempotency_and_missing(setup_test_environment):
    import hashlib
    raw = settings.bronze_path / "usdm" / "old.csv"
    raw.write_bytes(b"legacy")
    record = dict(file_id="legacy_1", client_id="client01", source="usdm", source_date="2020-01-01",
        original_filename="old.csv", stored_path=raw.relative_to(settings.BASE_DIR).as_posix(),
        sha256=hashlib.sha256(b"legacy").hexdigest(), size_bytes=6, received_at="2020-01-01T00:00:00Z", status="VERIFIED")
    path = metadata_manager.metadata_dir / "legacy.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    bad = dict(record, file_id="legacy_2", stored_path="data_lake/bronze/usdm/missing.csv")
    (path.parent / "missing.json").write_text(json.dumps(bad))
    (path.parent / "invalid.json").write_text("{")
    first = migrate_json()
    assert first["imported"] == ["legacy.json"] and len(first["errors"]) == 2
    assert (Path(first["backup"]) / "legacy.json").read_bytes() == path.read_bytes()
    second = migrate_json()
    assert second["skipped"] == ["legacy.json"] and not second["imported"]
    assert metadata_manager.list_all()[0].client_id == "client01" and raw.read_bytes() == b"legacy"


def test_old_multipart_fallback_and_new_key(client):
    response = client.post("/upload", headers={"X-API-Key": "test-only-collector"},
        data={"source": "noaa", "source_date": "2021-06-22"}, files={"file": ("old.csv", b"old")})
    assert response.status_code == 200 and response.json()["metadata"]["dataset_key"] == "old.csv"
    assert send(client, key="   ").status_code == 400
