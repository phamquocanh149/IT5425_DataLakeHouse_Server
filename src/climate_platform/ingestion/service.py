import hashlib
import logging
import os
import uuid
from pathlib import Path
from typing import Optional
from fastapi import HTTPException, UploadFile, status
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from climate_platform.catalog.repository import FileMetadata, metadata_manager
from climate_platform.config import settings
from climate_platform.ingestion.validation import (
    sanitize_filename,
    validate_source,
    validate_source_date,
)

logger = logging.getLogger("climate_platform.ingestion")


class IngestionResponse(BaseModel):
    status: str
    message: str
    metadata: Optional[FileMetadata] = None


async def process_file_upload(
    upload_file: UploadFile,
    source: str,
    source_date: str,
    client_id: str,
    dataset_key: Optional[str] = None,
) -> IngestionResponse:
    """Process file upload with chunked streaming, SHA-256 calculation, size enforcement,

    atomic placement into the Bronze data lake, and metadata recording.
    """
    valid_source = validate_source(source)
    valid_source_date = validate_source_date(source_date)
    safe_filename = sanitize_filename(upload_file.filename or "upload.bin")

    # Ensure storage paths exist
    settings.ensure_directories()

    # Generate temporary working file in data_lake/temp
    temp_file_id = str(uuid.uuid4())
    temp_path = settings.temp_path / f"upload_{temp_file_id}.tmp"

    hasher = hashlib.sha256()
    total_bytes = 0

    try:
        with open(temp_path, "wb") as temp_out:
            while True:
                chunk = await upload_file.read(settings.CHUNK_SIZE_BYTES)
                if not chunk:
                    break
                total_bytes += len(chunk)

                # Check max file size limit
                if total_bytes > settings.MAX_FILE_SIZE_BYTES:
                    logger.warning(
                        "Upload rejected from client '%s': file exceeded size limit (%d > %d bytes)",
                        client_id,
                        total_bytes,
                        settings.MAX_FILE_SIZE_BYTES,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB",
                    )

                hasher.update(chunk)
                temp_out.write(chunk)

            temp_out.flush()
            os.fsync(temp_out.fileno())

        if total_bytes == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty (0 bytes)",
            )

        calculated_sha256 = hasher.hexdigest()

        key = (
            dataset_key
            if dataset_key is not None
            else Path((upload_file.filename or "upload.bin").replace("\\", "/")).name
        )
        if not key.strip() or len(key) > 512 or any(ord(c) < 32 for c in key):
            raise HTTPException(400, "Invalid dataset_key")
        metadata, duplicate = await run_in_threadpool(
            metadata_manager.register_upload,
            temp_path,
            valid_source,
            valid_source_date,
            key,
            safe_filename,
            client_id,
            calculated_sha256,
            total_bytes,
        )
        return IngestionResponse(
            status="DUPLICATE" if duplicate else "VERIFIED",
            message="Logical observation already exists"
            if duplicate
            else "Bronze and registry committed",
            metadata=metadata,
        )

    except Exception:
        # Ensure cleanup of any temp file
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise
