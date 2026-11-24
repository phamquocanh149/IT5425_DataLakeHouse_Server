"""Filesystem Bronze repository for ``STORAGE_BACKEND=local``.

Owns every local-filesystem operation on raw Bronze payloads: resolving stored paths
(with containment), verifying bytes/size, and placing an uploaded temp file immutably.
Business/registry concerns stay in the catalog module.
"""

import hashlib
import os
from pathlib import Path

from fastapi import HTTPException

from climate_platform.config import settings


def _file_hash(path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class LocalObjectRepository:
    """Local Bronze object storage."""

    def resolve_raw(self, stored_path):
        path = (settings.BASE_DIR / stored_path).resolve()
        path.relative_to(settings.bronze_path.resolve())
        return path

    def verify_raw(self, stored_path, sha256, size):
        path = self.resolve_raw(stored_path)
        if not path.is_file() or path.stat().st_size != size or _file_hash(path) != sha256:
            raise HTTPException(503, "Stored content requires reconciliation")
        return path

    def place(self, source, sha256, size, temporary):
        path = settings.bronze_path / source / ("sha256=" + sha256) / "payload"
        path.resolve().relative_to(settings.bronze_path.resolve())
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.stat().st_size != size or _file_hash(path) != sha256:
                raise HTTPException(503, "Existing raw file requires reconciliation")
        else:
            # Retry-idempotent placement; an interrupted run can adopt after re-hashing.
            os.replace(temporary, path)
        return path.relative_to(settings.BASE_DIR).as_posix()
