"""Upload transfer: stream an upload to a temp file while hashing and capping size.

One job: stage the incoming bytes. It owns the chunked read loop, SHA-256 calculation, the
maximum-size enforcement, fsync of the temp file and cleanup of its own partial file when a
rejection happens. It raises ``IngestionError``; the controller maps that to HTTP.
"""

import hashlib
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from climate_platform.config import settings
from climate_platform.modules.ingestion.errors import IngestionError


@dataclass(frozen=True)
class StagedUpload:
    path: Path
    sha256: str
    size: int


async def stage_upload(upload_file) -> StagedUpload:
    settings.ensure_directories()
    temp_path = settings.temp_path / f"upload_{uuid.uuid4()}.tmp"
    hasher = hashlib.sha256()
    total = 0
    try:
        with open(temp_path, "wb") as temp_out:
            while True:
                chunk = await upload_file.read(settings.CHUNK_SIZE_BYTES)
                if not chunk:
                    break
                total += len(chunk)
                if total > settings.MAX_FILE_SIZE_BYTES:
                    raise IngestionError(
                        413,
                        "File exceeds maximum allowed size of "
                        f"{settings.MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB",
                    )
                hasher.update(chunk)
                temp_out.write(chunk)
            temp_out.flush()
            os.fsync(temp_out.fileno())
        if total == 0:
            raise IngestionError(400, "Uploaded file is empty (0 bytes)")
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
    return StagedUpload(path=temp_path, sha256=hasher.hexdigest(), size=total)
