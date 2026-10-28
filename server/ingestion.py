import hashlib
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple
from fastapi import HTTPException, UploadFile, status
from pydantic import BaseModel

from server.config import settings
from server.metadata import FileMetadata, metadata_manager

logger = logging.getLogger("climate_server.ingestion")

# Windows reserved device filenames
RESERVED_NAMES = {
    "con", "prn", "aux", "nul",
    "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9",
    "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9"
}


class IngestionResponse(BaseModel):
    status: str
    message: str
    metadata: Optional[FileMetadata] = None


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal, null bytes, and invalid Windows characters.

    Replaces invalid characters with underscores and guards against reserved Windows device names.
    """
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty or missing filename",
        )

    # Strip directory components (both / and \)
    base_name = Path(filename.replace("\\", "/")).name.strip()

    # Disallow null bytes
    if "\x00" in base_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename contains null byte characters",
        )

    # Sanitize characters: allow alphanumeric, dots, underscores, dashes
    sanitized = re.sub(r"[^a-zA-Z0-9._-]", "_", base_name)
    sanitized = sanitized.strip(". ")  # Remove leading/trailing dots/spaces

    if not sanitized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename becomes empty after sanitization",
        )

    stem = Path(sanitized).stem.lower()
    if stem in RESERVED_NAMES:
        sanitized = f"sanitized_{sanitized}"

    return sanitized


def validate_source(source: str) -> str:
    """Validate climate data source."""
    cleaned_source = source.strip().lower()
    if cleaned_source not in settings.ALLOWED_SOURCES:
        logger.warning("Rejected upload attempt for invalid source: '%s'", source)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source '{source}'. Must be one of: {', '.join(sorted(settings.ALLOWED_SOURCES))}",
        )
    return cleaned_source


def validate_source_date(source_date: str) -> str:
    """Validate source_date format (YYYY-MM-DD)."""
    try:
        parsed_date = datetime.strptime(source_date.strip(), "%Y-%m-%d")
        return parsed_date.strftime("%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source_date format '{source_date}'. Expected format: YYYY-MM-DD",
        )


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

        key = dataset_key if dataset_key is not None else Path((upload_file.filename or "upload.bin").replace("\\", "/")).name
        if not key.strip() or len(key) > 512 or any(ord(c) < 32 for c in key):
            raise HTTPException(400, "Invalid dataset_key")
        metadata, duplicate = metadata_manager.register_upload(
            temp_path, valid_source, valid_source_date, key, safe_filename,
            client_id, calculated_sha256, total_bytes)
        return IngestionResponse(status="DUPLICATE" if duplicate else "VERIFIED",
            message="Logical observation already exists" if duplicate else "Bronze and registry committed",
            metadata=metadata)

    except Exception:
        # Ensure cleanup of any temp file
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise
