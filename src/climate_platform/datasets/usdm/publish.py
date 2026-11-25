"""USDM auto-publish adapter: uploaded shapefile packages -> GIS replay -> artifacts."""

from __future__ import annotations

import csv
import os
import re
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path

from climate_platform.medallion.runner import medallion_lock
from climate_platform.modules.processing import auto_publish
from climate_platform.modules.processing.auto_publish import (
    PublishResult,
    download_records,
    prune_cache,
    record_order,
    record_targets,
    safe_record_name,
    tree_artifacts,
)

SIDECAR_SUFFIXES = (".shp", ".shx", ".dbf", ".prj", ".cpg")
GRID_FILENAME = "usdmfinal.csv"
GRID_RELATIVE = Path("gold") / "data" / GRID_FILENAME
# Packaged fallback so the automatic flow is self-contained, like NLDAS references.
DEFAULT_GRID = Path(__file__).with_name("resources") / "grid_reference.csv"
_WEEKLY = re.compile(r"^USDM_\d{8}\.", re.I)
_WEEKLY_DATE = re.compile(r"^USDM_(\d{8})", re.I)


def _weekly_record_date(record):
    """Return the week a weekly package/sidecar record represents, or ``None``."""
    try:
        name = safe_record_name(record.original_filename)
    except ValueError:
        return None
    if name.lower().endswith(".csv"):
        return None
    match = _WEEKLY_DATE.match(name)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%d").date().isoformat()
    except ValueError:
        return None


def _safe_extract(archive, target, grid_target=None):
    """Extract USDM packages, routing the reference CSV to ``gold/data``.

    Member paths are flattened on purpose (discovery expects sidecars in the shp folder),
    but every name is validated and every byte is counted against the zip-bomb limit.
    """
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        auto_publish.check_archive_limits(members)
        total = 0
        for member in members:
            parts = auto_publish.safe_archive_parts(member.filename)
            if member.is_dir():
                continue
            name = parts[-1]
            if name.casefold() == GRID_FILENAME and grid_target is not None:
                destination = Path(grid_target)
            else:
                destination = target / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            total += auto_publish.extract_member_limited(
                bundle,
                member,
                destination,
                max_bytes=auto_publish.MAX_ARCHIVE_UNCOMPRESSED_BYTES - total,
            )


def _looks_like_grid(path):
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            header = next(csv.reader(stream), [])
    except (OSError, UnicodeDecodeError, csv.Error):
        return False
    return {"grid", "lon", "lat"} <= {value.strip().lower() for value in header}


def _reference_uploads(uploads):
    """Exact ``usdmfinal.csv`` first, then any CSV carrying grid/lon/lat columns."""
    exact = [
        path
        for path in sorted(uploads.iterdir())
        if path.is_file() and path.name.casefold() == GRID_FILENAME
    ]
    if exact:
        return exact
    return [
        path
        for path in sorted(uploads.iterdir())
        if path.is_file() and path.suffix.lower() == ".csv" and _looks_like_grid(path)
    ]


def _prepare_source(uploads, source_root, fallback_grid=None):
    """Rebuild the replay source tree from current uploads and locate the grid reference.

    An uploaded/embedded reference always wins; a packaged grid is used only when Bronze
    carries none, so a standard shapefile-only upload can still build Gold automatically.
    """
    uploads, source_root = Path(uploads), Path(source_root)
    shp_dir = source_root / "bronze" / "data" / "shp"
    grid_target = source_root / GRID_RELATIVE
    if source_root.is_symlink():
        source_root.unlink()
    elif source_root.exists():
        shutil.rmtree(source_root)
    shp_dir.mkdir(parents=True, exist_ok=True)
    if uploads.is_dir():
        for path in sorted(uploads.iterdir()):
            if not path.is_file() or path.name.endswith(".sha256"):
                continue
            if path.suffix.lower() == ".zip":
                _safe_extract(path, shp_dir, grid_target)
            elif path.suffix.lower() in SIDECAR_SUFFIXES and _WEEKLY.match(path.name):
                shutil.copyfile(path, shp_dir / path.name)
        # A directly uploaded current grid record wins over a copy found inside an archive.
        references = _reference_uploads(uploads)
        if references:
            grid_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(references[0], grid_target)
    fallback = DEFAULT_GRID if fallback_grid is None else Path(fallback_grid)
    if not grid_target.is_file() and fallback.is_file():
        grid_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(fallback, grid_target)
    grid = grid_target if grid_target.is_file() else None
    return sorted(shp_dir.glob("USDM_*.shp")), grid


class UsdmPublisher:
    source = "usdm"

    def __init__(self, key_prefix="source=usdm", gis_python=None, start=None, end=None):
        self.key_prefix = key_prefix
        self.gis_python = gis_python or os.environ.get("USDM_GIS_PYTHON") or sys.executable
        self.start = start or os.environ.get("USDM_START")
        self.end = end or os.environ.get("USDM_END")

    def run(self, records, *, bronze_store, cache_root, log=print):
        result = PublishResult(source=self.source)
        current = [
            record
            for record in records
            if record.source == self.source
            and record.status == "VERIFIED"
            and record.is_current
            and record.s3_object_key
        ]
        result.bronze_records = len(current)
        cache_root = Path(cache_root)
        uploads = cache_root / "uploads"
        source_root = cache_root / "source"
        output_root = cache_root / "products"
        cache_root.mkdir(parents=True, exist_ok=True)

        def target_for(record):
            return uploads / safe_record_name(record.original_filename)

        with medallion_lock(
            cache_root / "publish.lock", f"USDM publisher already running ({cache_root})"
        ):
            try:
                result.bronze_downloaded, result.bronze_cached = download_records(
                    current, bronze_store, target_for, log=log
                )
                prune_cache(uploads, record_targets(current, bronze_store, target_for))
            except Exception as exc:
                result.failures["bronze_sync"] = f"{type(exc).__name__}: {exc}"
                return [], result

            try:
                shapefiles, grid = _prepare_source(uploads, source_root)
            except Exception as exc:
                result.failures["bronze_layout"] = f"{type(exc).__name__}: {exc}"
                return [], result
            if grid is None:
                result.reason = "missing USDM grid reference usdmfinal.csv"
                return [], result
            if not shapefiles:
                result.reason = "no USDM M shapefile packages in Bronze"
                return [], result

            from climate_platform.datasets.usdm.pipeline import run_pipeline

            # The Client already owns these Bronze rows; reuse them for build lineage
            # instead of re-registering the same dataset under a replay identity.
            records_by_date = {}
            for record in sorted(current, key=record_order):
                day = _weekly_record_date(record)
                if day is not None:
                    records_by_date[day] = record
            try:
                report = run_pipeline(
                    source_root,
                    output_root,
                    self.gis_python,
                    self.start,
                    self.end,
                    records=records_by_date,
                )
            except Exception as exc:
                result.failures["pipeline"] = f"{type(exc).__name__}: {exc}"
                return [], result
            result.ready = bool(report["succeeded"] or report["skipped"])
            result.details = report
            if report["failed"]:
                result.failures["pipeline"] = f"{report['failed']} week(s) failed"
            artifacts = []
            if report["succeeded"] or report["skipped"]:
                # product_path already stores source=usdm below each layer; strip it from the
                # root so the S3 key is source=usdm/week_date=..., not source=usdm/source=usdm.
                for layer in ("silver", "gold"):
                    root = output_root / layer / f"source={self.source}"
                    artifacts += tree_artifacts(layer, root, self.key_prefix)
            return artifacts, result
