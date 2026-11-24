"""Portal release publication workflow (offline; owns the DB <-> artifact orchestration).

Moved out of the release-store repository: the repository only reads release artifacts;
this service owns the publish pipeline (snapshot, lineage verification, product copy, GIS
index subprocess and activation). Call while ingestion writers are paused.
"""

import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from climate_platform.common.fs import contained
from climate_platform.common.hashing import file_hash
from climate_platform.entity.registry import Observation
from climate_platform.entity.warehouse import Build, GoldCell
from climate_platform.modules.portal.workers import prepare_gis
from climate_platform.repositories.database import connection
from climate_platform.repositories.releases import activate, dataset_id, snapshot


def copy_verified(source, target, expected):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    if file_hash(target) != expected or file_hash(source) != expected:
        raise ValueError("Artifact checksum mismatch while copying release")


def prepare_release(source, root, gis_python, release_id=None):
    """Call while ingestion writers are paused; locks Stage 3 runner during snapshot."""
    from climate_platform.datasets.usdm.processor import exclusive_run

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
    with connection(staging / "metadata/ingestion.sqlite3", mode="ro") as db:
        for row in (
            db.execute(
                select(Observation)
                .where(Observation.source == "usdm")
                .order_by(Observation.source_date)
            )
            .mappings()
            .all()
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
    with connection(staging / "products/warehouse.sqlite3", mode="ro") as db:
        for row in (
            db.execute(select(Build).order_by(Build.completed_at, Build.build_id)).mappings().all()
        ):
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
                    select(
                        GoldCell.time, GoldCell.grid, GoldCell.lon, GoldCell.lat, GoldCell.drought
                    )
                    .where(GoldCell.build_id == build["build_id"])
                    .order_by(GoldCell.time, GoldCell.grid)
                )
            ]
            if actual != expected:
                raise ValueError("Gold CSV/warehouse mismatch")
            catalog["builds"][build["build_id"]] = build
    (staging / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
    subprocess.run(
        [
            str(gis_python),
            str(Path(prepare_gis.__file__)),
            str(staging),
        ],
        check=True,
        timeout=600,
    )
    hashes = {
        p.relative_to(staging).as_posix(): file_hash(p) for p in staging.rglob("*") if p.is_file()
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
