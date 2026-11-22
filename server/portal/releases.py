"""Isolated, immutable serving releases. No test path is used by a live Portal."""

import csv
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import uuid
import zipfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from .store import PortalError, Store


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def dataset_id(source, key):
    return "ds_" + hashlib.sha256((source + "\0" + key).encode()).hexdigest()


def contained(root, relative):
    path = root / relative
    resolved = path.resolve()
    if root.resolve() not in resolved.parents or any(
        p.is_symlink() for p in [path, *path.parents] if p != root.parent
    ):
        raise PortalError(503, "ARTIFACT_UNAVAILABLE")
    return resolved


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


def copy_verified(source, target, expected):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    if sha256(target) != expected or sha256(source) != expected:
        raise ValueError("Artifact checksum mismatch while copying release")


def prepare_release(source, root, gis_python, release_id=None):
    """Call while ingestion writers are paused; locks Stage 3 runner during snapshot."""
    from server.usdm import exclusive_run

    source, root = Path(source).resolve(), Path(root).resolve()
    if source == root or source in root.parents or root in source.parents:
        raise ValueError("Release target and source must be disjoint")
    if any(p in {".test-runs", ".smoke", "data_crawl_USDM"} for p in root.parts):
        raise ValueError("Serving root cannot be source/test storage")
    rid = (
        release_id
        or "usdm-"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        + "-"
        + uuid.uuid4().hex[:8]
    )
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", rid):
        raise ValueError("Invalid release ID")
    staging = root / "staging" / rid
    final = root / "releases" / rid
    if staging.exists() or final.exists():
        raise ValueError("Release already exists")
    staging.mkdir(parents=True)
    with exclusive_run(source / "products"):
        snapshot(source / "metadata/ingestion.sqlite3", staging / "metadata/ingestion.sqlite3")
        snapshot(source / "products/warehouse.sqlite3", staging / "products/warehouse.sqlite3")
    catalog = {"datasets": {}, "observations": [], "builds": {}}
    with closing(sqlite3.connect(staging / "metadata/ingestion.sqlite3")) as db:
        db.row_factory = sqlite3.Row
        for row in db.execute(
            "SELECT * FROM observations WHERE source='usdm' ORDER BY source_date"
        ):
            record = dict(row)
            if record["s3_object_key"]:
                raise ValueError("Local Portal release requires local Bronze snapshot")
            did = dataset_id(record["source"], record["dataset_key"])
            catalog["datasets"][did] = {
                "dataset_id": did,
                "source": "usdm",
                "dataset_key": record["dataset_key"],
                "display_name": "USDM · CONUS",
                "description": "Hạn hán Hoa Kỳ · Dữ liệu quan sát theo tuần",
                "partition_kind": "week",
                "layers": ["bronze", "silver", "gold"],
            }
            raw = contained(source, record["stored_path"])
            dest = staging / record["stored_path"]
            if not dest.exists():
                copy_verified(raw, dest, record["sha256"])
            members = []
            with zipfile.ZipFile(dest) as archive:
                if (
                    len(archive.infolist()) > 256
                    or sum(i.file_size for i in archive.infolist()) > 128 * 1024 * 1024
                ):
                    raise ValueError("Unbounded Bronze ZIP")
                for item in sorted(archive.infolist(), key=lambda i: i.filename):
                    with archive.open(item) as stream:
                        digest = hashlib.file_digest(stream, "sha256").hexdigest()
                    members.append(
                        {
                            "name": item.filename,
                            "extension": Path(item.filename).suffix,
                            "size_bytes": item.file_size,
                            "sha256": digest,
                        }
                    )
            record.update(dataset_id=did, members=members)
            catalog["observations"].append(record)
    file_ids = {o["file_id"]: o for o in catalog["observations"]}
    with closing(sqlite3.connect(staging / "products/warehouse.sqlite3")) as db:
        db.row_factory = sqlite3.Row
        for row in db.execute("SELECT * FROM builds ORDER BY completed_at,build_id"):
            build = dict(row)
            if build["file_id"] not in file_ids:
                continue
            manifest = json.loads(build.pop("manifest"))
            obs = file_ids[build["file_id"]]
            if manifest["raw_sha256"] != obs["sha256"] or build["revision"] != obs["revision"]:
                raise ValueError("Build lineage mismatch")
            for member in obs["members"]:
                if manifest["source_members"].get(member["name"]) != member["sha256"]:
                    raise ValueError("Source member hash mismatch")
            build.update(recipe=manifest["recipe"], products={})
            for layer, product in manifest["products"].items():
                src = contained(source / "products", product["path"])
                relative = "products/" + product["path"]
                copy_verified(src, staging / relative, product["sha256"])
                build["products"][layer] = {
                    "path": relative,
                    "sha256": product["sha256"],
                    "size_bytes": src.stat().st_size,
                }
            # CSV and warehouse must be the same product, not merely the same row count.
            with (staging / build["products"]["gold"]["path"]).open(
                encoding="utf-8", newline=""
            ) as stream:
                expected = sorted(
                    (r["time"], r["grid"], float(r["lon"]), float(r["lat"]), r["drought"])
                    for r in csv.DictReader(stream)
                )
            actual = [
                tuple(r)
                for r in db.execute(
                    "SELECT time,grid,lon,lat,drought FROM gold_cells WHERE build_id=? ORDER BY time,grid",
                    (build["build_id"],),
                )
            ]
            if actual != expected:
                raise ValueError("Gold CSV/warehouse mismatch")
            catalog["builds"][build["build_id"]] = build
    (staging / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
    subprocess.run(
        [str(gis_python), str(Path(__file__).with_name("prepare_gis.py")), str(staging)],
        check=True,
        timeout=600,
    )
    hashes = {
        p.relative_to(staging).as_posix(): sha256(p) for p in staging.rglob("*") if p.is_file()
    }
    info = {
        "release_id": rid,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "status": "complete",
        "schema_version": 1,
        "hashes": hashes,
    }
    (staging / "release.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    final.parent.mkdir(parents=True, exist_ok=True)
    os.replace(staging, final)
    activate(root, rid)
    return info


def verify_release(root, rid):
    path = contained(Path(root), "releases/" + rid)
    info = read_json(path / "release.json")
    if info["status"] != "complete" or info["release_id"] != rid:
        raise ValueError("Incomplete release")
    for relative, digest in info["hashes"].items():
        if sha256(contained(path, relative)) != digest:
            raise ValueError("Release checksum mismatch: " + relative)
    return info


def activate(root, rid):
    verify_release(root, rid)
    store = Store(Path(root))
    store.initialize()
    with store.db() as db:
        db.execute("INSERT OR REPLACE INTO config VALUES ('active_release',?)", (rid,))
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
        if sha256(catalog_path) != self.info["hashes"]["catalog.json"]:
            raise PortalError(503, "ARTIFACT_UNAVAILABLE")
        self.catalog = read_json(catalog_path)
        self.rid = rid

    def verified(self, relative):
        path = contained(self.path, relative)
        if not path.is_file() or sha256(path) != self.info["hashes"].get(relative):
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
