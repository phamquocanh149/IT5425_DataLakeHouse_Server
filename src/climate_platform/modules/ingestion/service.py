"""Ingestion service: validate, stage and commit a collector upload to Bronze + registry.

One job: orchestrate validation, byte staging (``transfer``), catalog registration and the
response DTO. HTTP mapping lives in the controller; streaming/hashing/temp files live in
``transfer``; input validation lives in ``validation``.
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool

from climate_platform.modules.authorization.services.policy import allowed_sources
from climate_platform.modules.catalog.module import catalog_service
from climate_platform.modules.ingestion.dto import IngestionResponse
from climate_platform.modules.ingestion.transfer import stage_upload
from climate_platform.modules.ingestion.validation import (
    sanitize_filename,
    validate_dataset_key,
    validate_source,
    validate_source_date,
)

logger = logging.getLogger("climate_platform.ingestion")


class IngestionService:
    def __init__(self, catalog):
        self.catalog = catalog

    async def process_file_upload(
        self,
        upload_file: UploadFile,
        source: str,
        source_date: str,
        client_id: str,
        dataset_key: Optional[str] = None,
    ) -> IngestionResponse:
        """Validate, stage and commit one collector upload."""
        logger.info(
            "Received upload request from client '%s': filename='%s', source='%s', source_date='%s'",
            client_id,
            upload_file.filename,
            source,
            source_date,
        )
        valid_source = validate_source(source)
        valid_source_date = validate_source_date(source_date)
        safe_filename = sanitize_filename(upload_file.filename or "upload.bin")
        key = validate_dataset_key(
            dataset_key
            if dataset_key is not None
            else Path((upload_file.filename or "upload.bin").replace("\\", "/")).name
        )

        staged = await stage_upload(upload_file)
        try:
            metadata, duplicate = await run_in_threadpool(
                self.catalog.register_upload,
                staged.path,
                valid_source,
                valid_source_date,
                key,
                safe_filename,
                client_id,
                staged.sha256,
                staged.size,
            )
            return IngestionResponse(
                status="DUPLICATE" if duplicate else "VERIFIED",
                message="Logical observation already exists"
                if duplicate
                else "Bronze and registry committed",
                metadata=metadata,
            )
        except Exception:
            # The catalog removes the temp file on success; clean up on any failure.
            staged.path.unlink(missing_ok=True)
            raise

    async def list_uploads(self, client_id: str, source: Optional[str] = None):
        """List verified uploads, scoped to the caller's authorized sources."""
        logger.info("Client '%s' requested upload list (source_filter=%s)", client_id, source)
        return await run_in_threadpool(
            self.catalog.list_all,
            source_filter=source,
            client_id=None if client_id == "admin" else client_id,
            sources=None if client_id == "admin" else allowed_sources(client_id),
        )


async def process_file_upload(
    upload_file: UploadFile,
    source: str,
    source_date: str,
    client_id: str,
    dataset_key: Optional[str] = None,
) -> IngestionResponse:
    """Thin compatibility wrapper used by CLIs/tests; maps ingestion rejections to HTTP."""
    from fastapi import HTTPException

    from climate_platform.modules.ingestion.errors import IngestionError

    try:
        return await IngestionService(catalog_service).process_file_upload(
            upload_file=upload_file,
            source=source,
            source_date=source_date,
            client_id=client_id,
            dataset_key=dataset_key,
        )
    except IngestionError as exc:
        raise HTTPException(exc.status, exc.detail) from None
