"""Immutable Bronze object-key builder (layout is part of the compatibility contract)."""

import hashlib
import re
from datetime import date
from pathlib import Path

from climate_platform.config import settings


def object_key(source, source_date, dataset_key, revision, sha256, filename):
    if source not in settings.ALLOWED_SOURCES:
        raise ValueError("Unsupported source")
    day = date.fromisoformat(source_date)
    if day.isoformat() != source_date or revision < 1 or not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ValueError("Invalid object identity")
    if not dataset_key.strip() or len(dataset_key) > 512 or any(ord(c) < 32 for c in dataset_key):
        raise ValueError("Invalid dataset key")
    # Full hash is collision resistant and encodes even Unicode/path-like dataset IDs safely.
    dataset = hashlib.sha256(dataset_key.encode("utf-8")).hexdigest()
    suffix = Path(filename).suffix.lower()
    if not re.fullmatch(r"\.[a-z0-9]{1,16}", suffix):
        suffix = ".bin"
    return (
        f"source={source}/year={day.year:04d}/date={source_date}/dataset={dataset}/"
        f"revision={revision}/sha256={sha256}/raw{suffix}"
    )
