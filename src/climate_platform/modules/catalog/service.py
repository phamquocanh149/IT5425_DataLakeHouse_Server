"""Catalog service: business orchestration between the SQLite registry and object storage.

The local backend commits the registry and Bronze file together through the repository.
The S3 backend uses optimistic publication: object I/O never runs inside a writer
transaction, a competing revision may leave a retained (never deleted) orphan, and any
storage/verify failure fails closed.
"""

import logging
import uuid
from datetime import datetime, timezone

from climate_platform.config import settings
from climate_platform.entity.view import FileMetadata

logger = logging.getLogger("climate_platform.catalog")


class CatalogService:
    def __init__(self, repository, object_repository):
        self.repository = repository
        self.object_repository = object_repository

    @property
    def metadata_dir(self):
        return self.repository.metadata_dir

    @property
    def db_path(self):
        return self.repository.db_path

    def initialize(self):
        return self.repository.initialize()

    def connection(self):
        return self.repository.connection()

    def resolve_raw(self, stored_path):
        return self.repository.resolve_raw(stored_path)

    def get_by_file_id(self, file_id):
        return self.repository.get_by_file_id(file_id)

    def list_all(self, source_filter=None, client_id=None, sources=None):
        return self.repository.list_all(
            source_filter=source_filter, client_id=client_id, sources=sources
        )

    def register_upload(
        self, temporary, source, source_date, dataset_key, filename, client_id, sha256, size
    ):
        if settings.STORAGE_BACKEND == "s3":
            return self._register_s3(
                temporary, source, source_date, dataset_key, filename, client_id, sha256, size
            )
        return self.repository.register_local(
            temporary, source, source_date, dataset_key, filename, client_id, sha256, size
        )

    def _register_s3(
        self, temporary, source, source_date, dataset_key, filename, client_id, sha256, size
    ):
        from fastapi import HTTPException
        from botocore.exceptions import BotoCoreError, ClientError

        from climate_platform.s3.keys import object_key

        storage = self.object_repository()
        repo = self.repository
        identity = (source, source_date, dataset_key)
        try:
            # Optimistic publication: no DB connection/transaction spans S3 I/O.
            # A competing revision can leave a speculative orphan; never delete raw.
            for _ in range(8):
                current, previous = repo.state(identity, sha256, client_id)
                if previous:
                    record = FileMetadata(**previous)
                    if record.status != "VERIFIED" or not record.s3_object_key:
                        raise HTTPException(
                            503, "Stored content requires migration or reconciliation"
                        )
                    storage.verify(
                        record.s3_object_key, record.sha256, record.size_bytes, record.s3_bucket
                    )
                else:
                    revision = current["revision"] + 1 if current else 1
                    key = object_key(source, source_date, dataset_key, revision, sha256, filename)
                    version = storage.publish(temporary, key, sha256, size)
                    uri = f"s3://{storage.bucket}/{key}"
                    record = FileMetadata(
                        file_id="file_" + uuid.uuid4().hex,
                        source=source,
                        source_date=source_date,
                        dataset_key=dataset_key,
                        original_filename=filename,
                        client_id=client_id,
                        stored_path=uri,
                        sha256=sha256,
                        size_bytes=size,
                        received_at=datetime.now(timezone.utc).isoformat(),
                        revision=revision,
                        previous_file_id=current["file_id"] if current else None,
                        s3_bucket=storage.bucket,
                        s3_object_key=key,
                        s3_version_id=version,
                    )
                committed, duplicate = repo.commit_published(
                    record, identity, sha256, client_id, current, previous, size
                )
                if not committed:
                    continue
                temporary.unlink(missing_ok=True)
                return record, duplicate
            raise HTTPException(
                503, "Concurrent revision changes; retry later", headers={"Retry-After": "1"}
            )
        except (BotoCoreError, ClientError, ValueError) as exc:
            logger.warning("S3 verification failed: %s", type(exc).__name__)
            raise HTTPException(
                503, "Bronze storage unavailable or integrity check failed"
            ) from exc
