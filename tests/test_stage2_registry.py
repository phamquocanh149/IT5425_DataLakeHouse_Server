"""Stage 2: slow S3 must not monopolize SQLite; races preserve the wire contract."""

import asyncio
import hashlib
import io
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException, UploadFile

from climate_platform.catalog.repository import MetadataManager, metadata_manager
from climate_platform.catalog.s3_maintenance import migrate_bronze, reconcile_s3
from climate_platform.config import settings
from climate_platform.ingestion.service import process_file_upload
from tests.test_server import client, setup_test_environment  # noqa: F401


class MemoryS3:
    bucket = "stage2-test-bronze"

    def __init__(self):
        self.data = {}
        self.lock = threading.Lock()
        self.on_io = lambda: None

    def verify(self, key, sha256, size, bucket=None):
        self.on_io()
        body = self.data[key]
        assert len(body) == size and hashlib.sha256(body).hexdigest() == sha256
        return "test-version"

    def publish(self, path, key, sha256, size):
        self.on_io()
        with self.lock:
            self.data.setdefault(key, path.read_bytes())
        return self.verify(key, sha256, size)

    def objects(self):
        self.on_io()
        return [{"Key": key} for key in self.data]


@pytest.fixture
def storage(monkeypatch):
    fake = MemoryS3()
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr("climate_platform.infrastructure.object_store.S3Storage", lambda: fake)
    monkeypatch.setattr("climate_platform.catalog.s3_maintenance.S3Storage", lambda: fake)
    return fake


def send(content=b"raw", key="station", owner="collector01", filename="raw.csv"):
    return asyncio.run(
        process_file_upload(
            UploadFile(filename=filename, file=io.BytesIO(content)),
            "usdm",
            "2026-11-20",
            owner,
            key,
        )
    )


def assert_writer_available():
    # A real second connection, not a mock of SQLite's locking behavior.
    with sqlite3.connect(metadata_manager.db_path, timeout=0) as db:
        db.execute("BEGIN IMMEDIATE")
        db.rollback()


def test_publish_and_duplicate_verify_have_no_writer_lock(storage):
    storage.on_io = assert_writer_available
    first = send()
    assert send().status == "DUPLICATE"
    assert metadata_manager.get_by_file_id(first.metadata.file_id).status == "VERIFIED"


def test_slow_publish_allows_listing_and_other_dataset(storage):
    started, finish = threading.Event(), threading.Event()
    original = storage.publish

    def publish(path, key, sha, size):
        if path.read_bytes() == b"slow":
            started.set()
            assert finish.wait(5)
        return original(path, key, sha, size)

    storage.publish = publish
    with ThreadPoolExecutor(max_workers=2) as pool:
        slow = pool.submit(send, b"slow", "slow")
        try:
            assert started.wait(5)
            assert metadata_manager.list_all() == []
            assert pool.submit(send, b"fast", "fast").result(timeout=3).status == "VERIFIED"
        finally:
            finish.set()
        assert slow.result(timeout=5).status == "VERIFIED"


@pytest.mark.parametrize("same_content", [True, False])
def test_concurrent_publications_recheck_revision_and_hash(storage, same_content):
    barrier = threading.Barrier(2)
    original = storage.publish
    calls = 0
    lock = threading.Lock()

    def publish(*args):
        nonlocal calls
        with lock:
            calls += 1
            first_round = calls <= 2
        if first_round:
            barrier.wait(timeout=5)
        return original(*args)

    storage.publish = publish
    with ThreadPoolExecutor(max_workers=2) as pool:
        one = pool.submit(send, b"one")
        two = pool.submit(send, b"one" if same_content else b"two")
        results = [one.result(timeout=5), two.result(timeout=5)]
    rows = sorted(metadata_manager.list_all(), key=lambda r: r.revision)
    if same_content:
        assert sorted(r.status for r in results) == ["DUPLICATE", "VERIFIED"]
        assert len(rows) == 1 and len(storage.data) == 1
    else:
        assert [r.revision for r in rows] == [1, 2]
        assert rows[1].previous_file_id == rows[0].file_id
        assert [r.is_current for r in rows] == [False, True]
        # The losing speculative revision is retained for reconciliation, not deleted.
        assert len(reconcile_s3()["orphan_objects"]) == 1
        old = b"one" if rows[0].sha256 == hashlib.sha256(b"one").hexdigest() else b"two"
        assert send(old).metadata.file_id == rows[0].file_id
        assert metadata_manager.get_by_file_id(rows[1].file_id).is_current


def test_owner_is_rechecked_after_publish(storage):
    original = storage.publish
    entered = False

    def publish(*args):
        nonlocal entered
        if not entered:
            entered = True
            send(b"other-owner", owner="client01")
        return original(*args)

    storage.publish = publish
    with pytest.raises(HTTPException) as error:
        send()
    assert error.value.status_code == 403
    assert [r.client_id for r in metadata_manager.list_all()] == ["client01"]


def test_duplicate_status_is_rechecked_after_verify(storage):
    record = send().metadata
    original = storage.verify

    def verify(*args):
        result = original(*args)
        with metadata_manager.connection() as db:
            db.execute(
                "UPDATE observations SET status='CORRUPT' WHERE file_id=?", (record.file_id,)
            )
            db.commit()
        return result

    storage.verify = verify
    with pytest.raises(HTTPException) as error:
        send()
    assert error.value.status_code == 503


def test_commit_failure_keeps_object_for_retry_adoption(storage, monkeypatch):
    original_connect = sqlite3.connect

    class FailingCommit(sqlite3.Connection):
        def commit(self):
            raise sqlite3.OperationalError("injected commit failure")

    def connect(*args, **kwargs):
        if str(args[0]).split("?", 1)[0].endswith("ingestion.sqlite3"):
            kwargs["factory"] = FailingCommit
        return original_connect(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(sqlite3, "connect", connect)
        with pytest.raises(sqlite3.OperationalError):
            send()
    assert not metadata_manager.list_all() and len(storage.data) == 1
    assert send().status == "VERIFIED"
    assert len(storage.data) == 1 and not reconcile_s3()["orphan_objects"]


def test_busy_upload_returns_503_retry_after_and_listing_still_works(client, monkeypatch):
    monkeypatch.setattr(settings, "SQLITE_BUSY_TIMEOUT_SECONDS", 0.05)
    with sqlite3.connect(metadata_manager.db_path) as writer:
        writer.execute("BEGIN IMMEDIATE")
        listing = client.get("/uploads", headers={"X-API-Key": "test-only-collector"})
        assert listing.status_code == 200
        response = client.post(
            "/upload",
            headers={"X-API-Key": "test-only-collector"},
            data={"source": "usdm", "source_date": "2026-11-20"},
            files={"file": ("test.csv", b"raw")},
        )
        assert response.status_code == 503 and response.headers["Retry-After"] == "1"
    assert not metadata_manager.list_all()


def test_connection_never_creates_or_migrates_schema(tmp_path):
    manager = MetadataManager(tmp_path / "missing")
    with pytest.raises(sqlite3.OperationalError):
        with manager.connection():
            pass
    assert not manager.db_path.exists()
    manager.initialize()
    with sqlite3.connect(manager.db_path) as writer:
        writer.execute("BEGIN IMMEDIATE")
        # This would fail if connection() still attempted schema migration.
        with manager.connection() as reader:
            assert reader.execute("PRAGMA user_version").fetchone()[0] == 1
    manager.initialize()  # Explicit startup migration remains idempotent.


def test_s3_commit_busy_returns_retryable_and_adopts_orphan(client, storage, monkeypatch):
    monkeypatch.setattr(settings, "SQLITE_BUSY_TIMEOUT_SECONDS", 0.05)
    with sqlite3.connect(metadata_manager.db_path) as writer:
        writer.execute("BEGIN IMMEDIATE")
        response = client.post(
            "/upload",
            headers={"X-API-Key": "test-only-collector"},
            data={"source": "usdm", "source_date": "2026-11-20", "dataset_key": "station"},
            files={"file": ("raw.csv", b"raw")},
        )
        assert response.status_code == 503 and response.headers["Retry-After"] == "1"
    assert len(storage.data) == 1 and not metadata_manager.list_all()
    assert send().status == "VERIFIED"
    assert len(storage.data) == 1


def test_legacy_schema_is_migrated_explicitly(tmp_path):
    manager = MetadataManager(tmp_path)
    manager.initialize()
    with sqlite3.connect(manager.db_path) as db:
        for field in ("s3_bucket", "s3_object_key", "s3_version_id"):
            db.execute(f"ALTER TABLE observations DROP COLUMN {field}")
    manager.initialize()
    with manager.connection() as db:
        fields = {row[1] for row in db.execute("PRAGMA table_info(observations)")}
        assert {"s3_bucket", "s3_object_key", "s3_version_id"} <= fields


def test_migration_and_reconcile_release_writer_during_s3(storage, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    send()
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")
    storage.on_io = assert_writer_available
    assert not migrate_bronze(dry_run=False)["errors"]
    assert not reconcile_s3(repair=True)["missing"]
