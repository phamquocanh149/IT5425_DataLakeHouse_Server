"""Shared content hashing (SHA-256).

One implementation of the file-digest helper so the storage, catalog, release and
dataset layers do not each carry their own copy.
"""

import hashlib
from pathlib import Path


def file_hash(path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
