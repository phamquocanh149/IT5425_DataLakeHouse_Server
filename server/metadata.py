import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field

from server.config import settings
import sqlite3
import hashlib
import uuid
import time
from contextlib import contextmanager

logger = logging.getLogger("climate_server.metadata")


class FileMetadata(BaseModel):
    file_id: str = Field(..., description="Unique UUID for this uploaded file")
    source: str = Field(..., description="Climate data source (usdm, noaa, usgs, nldas)")
    source_date: str = Field(..., description="Observation or publication date (YYYY-MM-DD)")
    client_id: str = Field(..., description="Authenticated client identifier")
    original_filename: str = Field(..., description="Sanitized original filename")
    stored_path: str = Field(..., description="Relative storage path in data lake")
    size_bytes: int = Field(..., ge=0, description="File size in bytes")
    sha256: str = Field(..., min_length=64, max_length=64, description="Calculated SHA-256 checksum")
    received_at: str = Field(..., description="UTC ISO-8601 timestamp when received")
    dataset_key: str = ""
    revision: int = 1
    previous_file_id: Optional[str] = None
    is_current: bool = True
    error_message: Optional[str] = None
    status: str = Field("VERIFIED", description="Verification status (VERIFIED, DUPLICATE, etc.)")


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class MetadataManager:
    """Local SQLite registry; a short-lived connection per operation, never shared across threads."""
    def __init__(self, metadata_dir=None):
        self.metadata_dir = metadata_dir or settings.metadata_path

    @property
    def db_path(self):
        return self.metadata_dir / "ingestion.sqlite3"

    @contextmanager
    def connection(self):
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.db_path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            # First-open journal conversion can return SQLITE_BUSY immediately, even
            # with busy_timeout. Bound retries for concurrent initializers/processes.
            deadline = time.monotonic() + 30
            while True:
                try:
                    if db.execute("PRAGMA journal_mode").fetchone()[0] != "wal":
                        db.execute("PRAGMA journal_mode=WAL")
                    break
                except sqlite3.OperationalError as exc:
                    if "locked" not in str(exc).lower() or time.monotonic() >= deadline:
                        raise
                    time.sleep(0.05)
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA foreign_keys=ON")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise RuntimeError("Unsupported registry schema version")
            db.executescript('''
                CREATE TABLE IF NOT EXISTS content_blobs (
                    sha256 TEXT PRIMARY KEY, stored_path TEXT NOT NULL, size_bytes INTEGER NOT NULL CHECK(size_bytes>=0));
                CREATE TABLE IF NOT EXISTS observations (
                    file_id TEXT PRIMARY KEY, client_id TEXT NOT NULL,
                    source TEXT NOT NULL, source_date TEXT NOT NULL, dataset_key TEXT NOT NULL,
                    original_filename TEXT NOT NULL, stored_path TEXT NOT NULL,
                    sha256 TEXT NOT NULL REFERENCES content_blobs(sha256), size_bytes INTEGER NOT NULL,
                    received_at TEXT NOT NULL, status TEXT NOT NULL,
                    revision INTEGER NOT NULL CHECK(revision>=1), previous_file_id TEXT REFERENCES observations(file_id),
                    is_current INTEGER NOT NULL CHECK(is_current IN (0,1)),
                    error_message TEXT,
                    UNIQUE(source, source_date, dataset_key, sha256),
                    UNIQUE(source, source_date, dataset_key, revision));
                CREATE UNIQUE INDEX IF NOT EXISTS one_current_revision
                    ON observations(source,source_date,dataset_key) WHERE is_current=1;
                CREATE INDEX IF NOT EXISTS observation_owner ON observations(client_id,source);
                CREATE TABLE IF NOT EXISTS recovery_reports (
                    report_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, report_json TEXT NOT NULL);
                PRAGMA user_version=1;
            ''')
            yield db
        finally:
            db.close()

    def _insert(self, db, record):
        values = record.model_dump()
        fields = list(values)
        db.execute("INSERT INTO observations (" + ",".join(fields) + ") VALUES (" +
                   ",".join("?" for _ in fields) + ")", [values[k] for k in fields])

    def resolve_raw(self, stored_path):
        path = (settings.BASE_DIR / stored_path).resolve()
        path.relative_to(settings.bronze_path.resolve())
        return path

    def register_upload(self, temporary, source, source_date, dataset_key, filename, client_id, sha256, size):
        from fastapi import HTTPException
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            identity = (source, source_date, dataset_key)
            current = db.execute("SELECT * FROM observations WHERE source=? AND source_date=? AND dataset_key=? AND is_current=1", identity).fetchone()
            if current and current["client_id"] != client_id:
                raise HTTPException(403, "Dataset belongs to another identity")
            previous = db.execute("SELECT * FROM observations WHERE source=? AND source_date=? AND dataset_key=? AND sha256=?", (*identity, sha256)).fetchone()
            if previous:
                if previous["client_id"] != client_id:
                    raise HTTPException(403, "Observation belongs to another identity")
                record = FileMetadata(**dict(previous))
                path = self.resolve_raw(record.stored_path)
                if not path.is_file() or path.stat().st_size != size or file_hash(path) != sha256 or record.status != "VERIFIED":
                    raise HTTPException(503, "Stored content requires reconciliation")
                db.commit()
                temporary.unlink(missing_ok=True)
                return record, True
            blob = db.execute("SELECT * FROM content_blobs WHERE sha256=?", (sha256,)).fetchone()
            if blob:
                path = self.resolve_raw(blob["stored_path"])
                if not path.is_file() or file_hash(path) != sha256 or path.stat().st_size != size:
                    raise HTTPException(503, "Stored content requires reconciliation")
            else:
                path = settings.bronze_path / source / ("sha256=" + sha256) / "payload"
                path.resolve().relative_to(settings.bronze_path.resolve())
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.exists():
                    if path.stat().st_size != size or file_hash(path) != sha256:
                        raise HTTPException(503, "Existing raw file requires reconciliation")
                else:
                    # The SQLite writer lock serializes publishers. A rollback can leave an orphan,
                    # which reconciliation reports and a retry can safely adopt after hashing.
                    os.replace(temporary, path)
                db.execute("INSERT INTO content_blobs VALUES (?,?,?)", (sha256, path.relative_to(settings.BASE_DIR).as_posix(), size))
            record = FileMetadata(file_id="file_" + uuid.uuid4().hex,
                client_id=client_id, source=source, source_date=source_date, dataset_key=dataset_key,
                original_filename=filename, stored_path=path.relative_to(settings.BASE_DIR).as_posix(),
                sha256=sha256, size_bytes=size, received_at=datetime.now(timezone.utc).isoformat(),
                revision=current["revision"] + 1 if current else 1,
                previous_file_id=current["file_id"] if current else None)
            db.execute("UPDATE observations SET is_current=0 WHERE source=? AND source_date=? AND dataset_key=?", identity)
            self._insert(db, record)
            db.commit()
            temporary.unlink(missing_ok=True)
            return record, False

    def get_by_file_id(self, file_id):
        with self.connection() as db:
            row = db.execute("SELECT * FROM observations WHERE file_id=?", (file_id,)).fetchone()
            return FileMetadata(**dict(row)) if row else None

    def list_all(self, source_filter=None, client_id=None, sources=None):
        sql = "SELECT * FROM observations WHERE 1=1"
        params = []
        if source_filter:
            sql += " AND source=?"; params.append(source_filter)
        if client_id:
            sql += " AND client_id=?"; params.append(client_id)
        with self.connection() as db:
            rows = db.execute(sql + " ORDER BY received_at DESC", params).fetchall()
        return [FileMetadata(**dict(row)) for row in rows if sources is None or row["source"] in sources]


metadata_manager = MetadataManager()
