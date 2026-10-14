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

        # Check for duplicate file by SHA-256
        existing_record = metadata_manager.find_by_sha256(calculated_sha256)
        if existing_record:
            logger.info(
                "Duplicate file detected: sha256=%s already exists as file_id=%s (client=%s)",
                calculated_sha256,
                existing_record.file_id,
                client_id,
            )
            # Remove temp file
            if temp_path.exists():
                temp_path.unlink()

            return IngestionResponse(
                status="DUPLICATE",
                message="File with identical SHA-256 already exists in Bronze Data Lake",
                metadata=existing_record,
            )

        # Prepare bronze target partition directory:
        # data_lake/bronze/{source}/ingestion_date=YYYY-MM-DD/sha256=<checksum>/original_filename
        now_utc = datetime.now(timezone.utc)
        ingestion_date = now_utc.strftime("%Y-%m-%d")

        target_dir = (
            settings.bronze_path
            / valid_source
            / f"ingestion_date={ingestion_date}"
            / f"sha256={calculated_sha256}"
        )
        target_dir.mkdir(parents=True, exist_ok=True)
        final_file_path = target_dir / safe_filename

        # Prevent escaping bronze directory (path traversal check)
        try:
            final_file_path.resolve().relative_to(settings.bronze_path.resolve())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Security violation: destination path escapes Bronze storage",
            )

        # Atomically move temp file to Bronze target path
        os.replace(temp_path, final_file_path)

        # Prepare metadata
        relative_stored_path = str(final_file_path.relative_to(settings.BASE_DIR)).replace("\\", "/")
        file_id = f"file_{uuid.uuid4().hex[:16]}"
        received_at_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

        metadata = FileMetadata(
            file_id=file_id,
            source=valid_source,
            source_date=valid_source_date,
            client_id=client_id,
            original_filename=safe_filename,
            stored_path=relative_stored_path,
            size_bytes=total_bytes,
            sha256=calculated_sha256,
            received_at=received_at_iso,
            status="VERIFIED",
        )

        # Atomically record metadata
        metadata_manager.save_metadata(metadata)

        logger.info(
            "Upload VERIFIED: file_id=%s, source=%s, sha256=%s, bytes=%d, client=%s",
            file_id,
            valid_source,
            calculated_sha256,
            total_bytes,
            client_id,
        )

        return IngestionResponse(
            status="VERIFIED",
            message="File ingested and verified successfully into Bronze Data Lake",
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
