"""SQLAlchemy registry repository for the ingestion catalog (``ingestion.sqlite3``).

Only SQL and the local-registry commit path live here; object storage is handled by the
``s3`` package and the optimistic DB <-> object-storage orchestration by
``modules.catalog.service``.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import insert, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from climate_platform.config import settings
from climate_platform.entity import registry as _registry  # noqa: F401  (populate metadata)
from climate_platform.entity.registry import ContentBlob, Observation, RegistryBase
from climate_platform.entity.view import FileMetadata
from climate_platform.repositories.database import (
    connection as db_connection,
    engine_for,
    retry_locked,
)
from climate_platform.s3.local_repository import LocalObjectRepository

logger = logging.getLogger("climate_platform.catalog")


class MetadataManager:
    """Local SQLite registry; a short-lived connection per operation, never shared across threads."""

    def __init__(self, metadata_dir=None, local=None):
        self.metadata_dir = metadata_dir or settings.metadata_path
        self.local = local or LocalObjectRepository()

    @property
    def db_path(self):
        return self.metadata_dir / "ingestion.sqlite3"

    def initialize(self):
        """Create/migrate once at startup (or explicitly in an offline CLI)."""
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        # First-open journal conversion can return SQLITE_BUSY immediately; bound retries
        # for concurrent initializers/processes.
        retry_locked(
            lambda: RegistryBase.metadata.create_all(
                engine_for(self.db_path, mode="rwc", busy_timeout=30)
            ),
            timeout=30,
        )
        with db_connection(self.db_path, busy_timeout=30) as db:
            version = db.execute("PRAGMA user_version").fetchone()["user_version"]
            if version not in (0, 1):
                raise RuntimeError("Unsupported registry schema version")
            columns = {
                row["name"] for row in db.execute("PRAGMA table_info(observations)").fetchall()
            }
            # Additive migration under a writer lock; legacy paths and blob records are retained.
            db.execute("BEGIN IMMEDIATE")
            for column in ("s3_bucket", "s3_object_key", "s3_version_id"):
                if column not in columns:
                    db.execute(f"ALTER TABLE observations ADD COLUMN {column} TEXT")
            db.execute("PRAGMA user_version=1")
            db.commit()

    def connection(self):
        """Open an existing registry; requests never create or migrate schema."""
        return db_connection(self.db_path)

    def _state(self, db, identity, sha256, client_id):
        from fastapi import HTTPException

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
        previous = (
            db.execute(
                select(Observation).where(
                    Observation.source == identity[0],
                    Observation.source_date == identity[1],
                    Observation.dataset_key == identity[2],
                    Observation.sha256 == sha256,
                )
            )
            .mappings()
            .first()
        )
        current = dict(current) if current else None
        previous = dict(previous) if previous else None
        if any(row and row["client_id"] != client_id for row in (current, previous)):
            raise HTTPException(403, "Dataset belongs to another identity")
        return current, previous

    def _insert(self, db, record):
        values = record.model_dump() if hasattr(record, "model_dump") else dict(record)
        values["is_current"] = int(bool(values.get("is_current", True)))
        db.execute(insert(Observation).values(**values))

    def state(self, identity, sha256, client_id):
        """Read the current/previous observation for a dataset identity in one snapshot.

        Opens a short read transaction so the two reads stay consistent; no object I/O.
        """
        with self.connection() as db:
            db.execute("BEGIN")
            return self._state(db, identity, sha256, client_id)

    def commit_published(self, record, identity, sha256, client_id, current, previous, size):
        """Atomically commit an already-published object as the new current revision.

        The DB transaction never spans object I/O: the caller publishes/verifies first and
        passes the closure of the state it read. Returns ``(committed, duplicate)``; a
        competing revision leaves ``committed`` false so the caller retries.
        """
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            latest, duplicate_row = self._state(db, identity, sha256, client_id)
            if previous:
                # Reconcile/migration/revision may have changed this receipt while the
                # caller's verify was in flight. Re-read and retry against the new mapping.
                if duplicate_row != previous:
                    return False, False
            else:
                if duplicate_row or latest != current:
                    return False, False
                db.execute(
                    sqlite_insert(ContentBlob)
                    .values(sha256=sha256, stored_path=record.stored_path, size_bytes=size)
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
                self._insert(db, record)
            db.commit()
        return True, previous is not None

    def resolve_raw(self, stored_path):
        return self.local.resolve_raw(stored_path)

    def register_local(
        self, temporary, source, source_date, dataset_key, filename, client_id, sha256, size
    ):
        from fastapi import HTTPException

        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            identity = (source, source_date, dataset_key)
            current, previous = self._state(db, identity, sha256, client_id)
            if previous:
                record = FileMetadata(**previous)
                self.local.verify_raw(record.stored_path, sha256, size)
                if record.status != "VERIFIED":
                    raise HTTPException(503, "Stored content requires reconciliation")
                duplicate = True
            else:
                blob = (
                    db.execute(select(ContentBlob).where(ContentBlob.sha256 == sha256))
                    .mappings()
                    .first()
                )
                if blob:
                    blob = dict(blob)
                    self.local.verify_raw(blob["stored_path"], sha256, size)
                    stored_path = blob["stored_path"]
                else:
                    stored_path = self.local.place(source, sha256, size, temporary)
                    db.execute(
                        insert(ContentBlob).values(
                            sha256=sha256, stored_path=stored_path, size_bytes=size
                        )
                    )
                record = FileMetadata(
                    file_id="file_" + uuid.uuid4().hex,
                    client_id=client_id,
                    source=source,
                    source_date=source_date,
                    dataset_key=dataset_key,
                    original_filename=filename,
                    stored_path=stored_path,
                    sha256=sha256,
                    size_bytes=size,
                    received_at=datetime.now(timezone.utc).isoformat(),
                    revision=current["revision"] + 1 if current else 1,
                    previous_file_id=current["file_id"] if current else None,
                )
                db.execute(
                    update(Observation)
                    .where(
                        Observation.source == source,
                        Observation.source_date == source_date,
                        Observation.dataset_key == dataset_key,
                    )
                    .values(is_current=0)
                )
                self._insert(db, record)
                duplicate = False
            db.commit()
        temporary.unlink(missing_ok=True)
        return record, duplicate

    def get_by_file_id(self, file_id):
        with self.connection() as db:
            row = (
                db.execute(select(Observation).where(Observation.file_id == file_id))
                .mappings()
                .first()
            )
            return FileMetadata(**dict(row)) if row else None

    def list_all(self, source_filter=None, client_id=None, sources=None):
        statement = select(Observation)
        if source_filter:
            statement = statement.where(Observation.source == source_filter)
        if client_id:
            statement = statement.where(Observation.client_id == client_id)
        statement = statement.order_by(Observation.received_at.desc())
        with self.connection() as db:
            rows = [dict(row) for row in db.execute(statement).mappings().all()]
        return [FileMetadata(**row) for row in rows if sources is None or row["source"] in sources]


metadata_manager = MetadataManager()
