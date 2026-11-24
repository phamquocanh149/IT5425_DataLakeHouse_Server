"""Safe local IO primitives for the medallion layers.

One home for the atomic-write, completion-marker and checksum helpers that every dataset
pipeline used to copy (``write_json_atomic``, ``atomic_json``, ``sha256_file``). Content
hashing stays in ``common.hashing`` and is re-exported here so a layer imports a single
``medallion.io``.

Writes are atomic (temp file + ``os.replace``) and a stage publishes a completion marker
only after every output exists, so a run interrupted mid-write never leaves a final file
that a later run mistakes for finished work.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path

from climate_platform.common.hashing import file_hash

__all__ = [
    "file_hash",
    "read_json",
    "write_json_atomic",
    "write_text_atomic",
    "atomic_write",
    "atomic_replace",
    "outputs_complete",
    "write_completion_marker",
    "sha256",
]


def read_json(path) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def atomic_replace(source, target) -> None:
    """Rename ``source`` onto ``target`` (same filesystem) after flushing to disk."""
    source, target = Path(source), Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source, target)
    _fsync_dir(target.parent)


def _fsync_dir(path: Path) -> None:
    """Best-effort directory fsync so a completed rename survives a crash (POSIX)."""
    try:
        handle = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(handle)
    except OSError:
        pass
    finally:
        os.close(handle)


@contextmanager
def atomic_write(target, *, suffix=".tmp"):
    """Yield a temporary path; on success flush its bytes and rename onto ``target``.

    The body writes to the yielded path. If it raises, or the process dies, ``target`` is
    left untouched (never a truncated file), so a scheduled rerun cannot read a partial
    output as complete.
    """
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + suffix)
    try:
        yield temporary
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    atomic_replace(temporary, target)


def write_text_atomic(path, text) -> None:
    """Write text without leaving a partial file for a scheduled rerun to read."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    atomic_replace(temporary, target)


def write_json_atomic(path, payload) -> None:
    """Write JSON without leaving a partial file for a scheduled rerun to read."""
    write_text_atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def outputs_complete(root, marker, expected) -> bool:
    """True only when ``root/marker`` records every ``expected`` file at its recorded size.

    A missing marker (never finished, or deleted at the start of a rebuild) or a size
    mismatch (truncated/corrupt output) both mean the stage is not complete and must rebuild.
    """
    root = Path(root)
    try:
        recorded = read_json(root / marker)
    except (OSError, ValueError):
        return False
    files = recorded.get("files") if isinstance(recorded, dict) else None
    if not isinstance(files, dict):
        return False
    for name in expected:
        info = files.get(name)
        path = root / name
        if not isinstance(info, dict) or not path.is_file():
            return False
        if path.stat().st_size != info.get("size_bytes"):
            return False
    return True


def write_completion_marker(root, marker, files) -> None:
    """Publish the stage completion marker last, after all ``files`` exist on disk."""
    payload = {
        "files": {
            name: {"size_bytes": Path(path).stat().st_size, "sha256": file_hash(path)}
            for name, path in files.items()
        }
    }
    write_json_atomic(Path(root) / marker, payload)


def sha256(path) -> str:
    """Chunked file digest; the single checksum helper used by the medallion layers."""
    return file_hash(path)
