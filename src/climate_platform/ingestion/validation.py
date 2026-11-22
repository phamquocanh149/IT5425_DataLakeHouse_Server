"""Upload input validation: source, source_date and safe filenames."""

import logging
import re
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, status

from climate_platform.config import settings

logger = logging.getLogger("climate_platform.ingestion")

# Windows reserved device filenames
RESERVED_NAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    "com1",
    "com2",
    "com3",
    "com4",
    "com5",
    "com6",
    "com7",
    "com8",
    "com9",
    "lpt1",
    "lpt2",
    "lpt3",
    "lpt4",
    "lpt5",
    "lpt6",
    "lpt7",
    "lpt8",
    "lpt9",
}


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
