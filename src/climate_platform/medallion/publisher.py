"""Atomic, checksum-verified publication of immutable layer products.

One job: given a produced payload and its expected digest, place it at the product path
without ever overwriting a different payload and without leaving a partial file. Shared by
every dataset processor so write-then-verify ordering and the "adopt a verified orphan,
reject a mismatched file" rule are defined in exactly one place.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from climate_platform.common.hashing import file_hash

__all__ = ["file_hash", "publish_atomic", "product_path"]


def publish_atomic(source, destination, digest: str) -> Path:
    """Copy ``source`` to ``destination`` atomically; adopt verified orphans, never overwrite.

    If the destination already exists with the expected ``digest`` it is adopted as-is
    (idempotent retry); a mismatched existing file is refused.
    """
    source, destination = Path(source), Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if file_hash(destination) != digest:
            raise ValueError("Existing product checksum mismatch")
        return destination
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    with source.open("rb") as inp, temporary.open("wb") as out:
        shutil.copyfileobj(inp, out)
        out.flush()
        os.fsync(out.fileno())
    os.replace(temporary, destination)
    return destination


def product_path(layer: str, source: str, day: str, build: str, digest: str, suffix: str) -> Path:
    """Immutable product layout shared by every dataset: layer/source/week/build/digest."""
    return (
        Path(layer)
        / f"source={source}"
        / f"week_date={day}"
        / f"build={build}"
        / f"{digest}{suffix}"
    )
