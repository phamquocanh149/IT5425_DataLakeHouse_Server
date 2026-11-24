"""Isolated, immutable serving releases (release artifact store).

Reads release snapshots (standalone SQLite files and the JSON release manifests) via ORM
statements on a read-only connection to the copied database; never touches the live
registry. Building a release (snapshot + lineage verification + product copy) is a
service-level workflow and lives in ``modules.portal.services.publish``.
"""

import hashlib
import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path

from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from climate_platform.common.errors import PortalError
from climate_platform.common.fs import contained
from climate_platform.common.hashing import file_hash
from climate_platform.entity.control import Config
from climate_platform.repositories.control_repository import Store

# Backward-compatible alias for existing callers/tests.
sha256 = file_hash


def dataset_id(source, key):
    return "ds_" + hashlib.sha256((source + "\0" + key).encode()).hexdigest()


def read_json(path, maximum=16 * 1024 * 1024):
    if path.stat().st_size > maximum:
        raise PortalError(413, "PREVIEW_TOO_LARGE")
    return json.loads(path.read_text(encoding="utf-8"))


def snapshot(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as src:
        with closing(sqlite3.connect(target)) as dst:
            src.backup(dst)
            dst.execute("PRAGMA journal_mode=DELETE")


def verify_release(root, rid):
    path = contained(Path(root), "releases/" + rid)
    info = read_json(path / "release.json")
    if info["status"] != "complete" or info["release_id"] != rid:
        raise ValueError("Incomplete release")
    for relative, digest in info["hashes"].items():
        if file_hash(contained(path, relative)) != digest:
            raise ValueError("Release checksum mismatch: " + relative)
    return info


def activate(root, rid):
    verify_release(root, rid)
    store = Store(Path(root))
    store.initialize()
    with store.db() as db:
        db.execute(
            sqlite_insert(Config)
            .values(key="active_release", value=rid)
            .on_conflict_do_update(index_elements=[Config.key], set_={"value": rid})
        )
        store.audit(db, "operator-cli", "activate_release", rid)


class Release:
    def __init__(self, root, rid):
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", rid):
            raise PortalError(404, "RESOURCE_NOT_FOUND")
        self.path = contained(root, "releases/" + rid)
        if not self.path.exists():
            raise PortalError(410, "RELEASE_EXPIRED")
        self.info = read_json(self.path / "release.json")
        if self.info.get("status") != "complete":
            raise PortalError(503, "STORAGE_UNAVAILABLE")
        catalog_path = self.path / "catalog.json"
        if file_hash(catalog_path) != self.info["hashes"]["catalog.json"]:
            raise PortalError(503, "ARTIFACT_UNAVAILABLE")
        self.catalog = read_json(catalog_path)
        self.rid = rid

    def verified(self, relative):
        path = contained(self.path, relative)
        if not path.is_file() or file_hash(path) != self.info["hashes"].get(relative):
            raise PortalError(503, "ARTIFACT_UNAVAILABLE")
        return path

    def latest(self, obs):
        builds = [b for b in self.catalog["builds"].values() if b["file_id"] == obs["file_id"]]
        return max(builds, key=lambda b: (b["completed_at"], b["build_id"]), default=None)

    def observations(self, did, current=True):
        return [
            o
            for o in self.catalog["observations"]
            if o["dataset_id"] == did and (not current or o["is_current"])
        ]
