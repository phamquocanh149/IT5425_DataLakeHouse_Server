"""One cross-platform exclusive OS lock for the medallion pipelines.

Every dataset runner used to carry its own ``exclusive_run``/``_lock`` copy (NOAA, NLDAS,
USGS, USDM, backup). This is the single implementation. It raises the underlying OS error
(``BlockingIOError`` on POSIX, ``OSError`` on Windows) when the lock is held; callers that
want a friendlier message translate it themselves.

The lock is an advisory file lock that the OS releases even if the process dies, so an
abandoned lock file is never a stale lock.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

__all__ = ["exclusive_run"]


@contextmanager
def exclusive_run(path):
    """Hold a non-blocking exclusive lock on the file at ``path`` for the block scope."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a+b") as stream:
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            if not stream.read(1):
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
