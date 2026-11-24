"""USDM Bronze discovery and packaging.

One job: find the source shapefiles, package each week's sidecars into a deterministic ZIP,
and materialize a Bronze record back to a local file (S3 or registry path). Bronze stays
immutable; nothing here writes Silver/Gold.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import zipfile
from datetime import datetime

from climate_platform.medallion.io import file_hash
from climate_platform.s3.module import object_repository

DATASET_KEY = "usdm/gis/CONUS/M/weekly"


def discover(source, start=None, end=None):
    weeks = {}
    for path in sorted((source / "bronze/data/shp").rglob("USDM_*.shp")):
        match = re.fullmatch(r"USDM_(\d{8})\.shp", path.name)
        if not match:
            continue
        day = datetime.strptime(match[1], "%Y%m%d").date().isoformat()
        if (start and day < start) or (end and day > end):
            continue
        if day in weeks:
            raise ValueError(f"Ambiguous shapefile for {day}")
        weeks[day] = path
    if not weeks:
        raise ValueError("No USDM M shapefiles found in selected date range")
    return weeks


def package_raw(shp, target):
    """Deterministic transport container; every original sidecar byte is retained."""
    members = sorted(shp.parent.glob(shp.stem + ".*"))
    if not {".shp", ".shx", ".dbf", ".prj"} <= {p.suffix.lower() for p in members}:
        raise ValueError("Incomplete shapefile package")
    manifest = {}
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in members:
            before = file_hash(path)
            info = zipfile.ZipInfo(path.name, date_time=(1980, 1, 1, 0, 0, 0))
            digest = hashlib.sha256()
            with path.open("rb") as source, archive.open(info, "w") as output:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
                    output.write(chunk)
            if before != digest.hexdigest() or before != file_hash(path):
                raise ValueError("Source changed while snapshotting")
            manifest[path.name] = before
    return manifest


def materialize_raw(manager, record, target):
    if record.s3_object_key:
        storage = object_repository()
        try:
            kwargs = {"Bucket": record.s3_bucket, "Key": record.s3_object_key}
            if record.s3_version_id:
                kwargs["VersionId"] = record.s3_version_id
            response = storage.get_object(**kwargs)
            with response["Body"] as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
        finally:
            storage.client.close()
    else:
        shutil.copyfile(manager.resolve_raw(record.stored_path), target)
    if target.stat().st_size != record.size_bytes or file_hash(target) != record.sha256:
        raise ValueError("Bronze checksum mismatch")
