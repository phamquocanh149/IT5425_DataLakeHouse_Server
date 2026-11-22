"""Atomic, checksum-verified publication of immutable layer products.

Shared by dataset processors so product paths, write-then-verify ordering and the
"never overwrite a different payload" rule are defined in exactly one place. Product
layout and hashes are unchanged from the original USDM pipeline.
"""

import hashlib
import os
import shutil
from pathlib import Path


def file_hash(path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def publish_atomic(source: Path, destination: Path, digest: str, *, verify) -> None:
    """Copy ``source`` to ``destination`` atomically; adopt verified orphans, never overwrite.

    ``verify(root, manifest)`` is supplied by the caller to re-check the artifact set;
    it is invoked by the caller, not here, to keep product/lineage knowledge out of this
    generic helper.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if file_hash(destination) != digest:
            raise ValueError("Existing product checksum mismatch")
        return
    temp = destination.with_suffix(".tmp")
    with source.open("rb") as inp, temp.open("wb") as out:
        shutil.copyfileobj(inp, out)
        out.flush()
        os.fsync(out.fileno())
    os.replace(temp, destination)


def product_path(layer: str, source: str, day: str, build: str, digest: str, suffix: str) -> Path:
    return (
        Path(layer)
        / f"source={source}"
        / f"week_date={day}"
        / f"build={build}"
        / f"{digest}{suffix}"
    )
