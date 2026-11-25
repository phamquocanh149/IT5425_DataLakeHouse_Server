"""USDM medallion orchestration (Bronze -> Silver -> Gold replay).

One job: drive the per-week replay — package Bronze, compute the build identity, skip a
completed build (verified), run the GIS worker, publish products, then commit the warehouse
row — under one OS lock. Science is in ``science.py``; publication in ``publisher.py``;
warehouse access in ``warehouse.py``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from climate_platform.config import settings
from climate_platform.datasets.usdm.bronze import (
    DATASET_KEY,
    discover,
    materialize_raw,
    package_raw,
)
from climate_platform.datasets.usdm.publisher import publish_products, verify_products
from climate_platform.datasets.usdm.recipe import prepare_recipe
from climate_platform.datasets.usdm.warehouse import (
    commit_build,
    existing_manifest,
    initialize_catalog,
    record_attempt,
)
from climate_platform.datasets.usdm.worker import run_worker
from climate_platform.medallion.io import file_hash
from climate_platform.medallion.lock import exclusive_run as _os_exclusive_run
from climate_platform.modules.catalog.service import CatalogService
from climate_platform.repositories.catalog_repository import MetadataManager
from climate_platform.s3.module import object_repository

logger = logging.getLogger("climate_platform.usdm")


@contextmanager
def exclusive_run(root):
    """Directory-scoped replay lock; the OS releases it even on process death."""
    with _os_exclusive_run(Path(root) / "pipeline.lock"):
        yield


def run_pipeline(source, root, python, start=None, end=None, records=None):
    """Run the replay. ``records`` maps a source date to the Bronze record already stored
    for an automatic publish, so the caller's upload is reused instead of re-registered."""
    source, root = Path(source).resolve(), Path(root).resolve()
    if source == root or source in root.parents or root in source.parents:
        raise ValueError("Pipeline output and source must be disjoint")
    for destination in (settings.bronze_path, settings.metadata_path):
        destination = destination.resolve()
        if destination == source or source in destination.parents:
            raise ValueError("Server storage must not write into the source repository")
    for value in (start, end):
        if value and date.fromisoformat(value).isoformat() != value:
            raise ValueError("Dates must be YYYY-MM-DD")
    weeks = discover(source, start, end)
    root.mkdir(parents=True, exist_ok=True)
    with exclusive_run(root):
        return _run(source, root, python, weeks, records)


def _run(source, root, python, weeks, records=None):
    records = dict(records or {})
    manager = CatalogService(MetadataManager(), object_repository)
    manager.initialize_once()
    catalog = root / "warehouse.sqlite3"
    initialize_catalog(catalog)
    report = {"succeeded": 0, "skipped": 0, "failed": 0, "weeks": []}
    with tempfile.TemporaryDirectory(dir=root, prefix="work-") as directory:
        work = Path(directory)
        cleaner, grid, recipe = prepare_recipe(source, root, work, python, run_worker)
        for day, shp in weeks.items():
            try:
                status = process_week(
                    manager,
                    catalog,
                    root,
                    work,
                    python,
                    cleaner,
                    grid,
                    recipe,
                    day,
                    shp,
                    record=records.get(day),
                )
                report[status] += 1
                detail = ""
                logger.info("usdm week=%s status=%s", day, status)
            except Exception as exc:
                status, detail = "failed", str(exc)
                report["failed"] += 1
                logger.error("usdm week=%s status=failed error_type=%s", day, type(exc).__name__)
            record_attempt(catalog, day, status, detail)
            report["weeks"].append({"date": day, "status": status, "error": detail})
    report_path = root / "last_run.json"
    temporary = root / "last_run.tmp"
    temporary.write_text(json.dumps(report, indent=2), encoding="utf-8")
    os.replace(temporary, report_path)
    return report


def process_week(
    manager, catalog, root, work, python, cleaner, grid, recipe, day, shp, record=None
):
    with tempfile.TemporaryDirectory(dir=work, prefix=day) as directory:
        stage = Path(directory)
        raw = stage / (shp.stem + "_M.zip")
        members = package_raw(shp, raw)
        size, sha = raw.stat().st_size, file_hash(raw)
        if size > settings.MAX_FILE_SIZE_BYTES:
            raise ValueError("USDM package exceeds configured ingestion limit")
        reused = record is not None
        if not reused:
            # Offline replay owns the rows it registers; the auto flow reuses the Client
            # record instead, because re-registering under a replay identity is rejected.
            record, _ = manager.register_upload(
                raw, "usdm", day, DATASET_KEY, raw.name, "usdm-replay", sha, size
            )
            identity = {"file_id": record.file_id, "raw_sha256": sha, "recipe": recipe}
            raw_sha = sha
        else:
            identity = {
                "file_id": record.file_id,
                "raw_sha256": record.sha256,
                "package_sha256": sha,
                "recipe": recipe,
            }
            raw_sha = record.sha256
        build = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        existing = existing_manifest(catalog, build)
        if existing:
            verify_products(root, existing)
            return "skipped"
        if not reused:
            materialize_raw(manager, record, raw)
        run_worker(
            python,
            ["--cleaner", cleaner, "--raw", raw, "--day", day, "--grid", grid, "--output", stage],
        )
        manifest = {
            **identity,
            "revision": record.revision,
            "source_date": day,
            "source_members": members,
            "products": {},
        }
        manifest["products"] = publish_products(root, stage, grid, build, day)
        verify_products(root, manifest)
        # All artifacts exist before the single atomic warehouse commit. An interrupted
        # build leaves unreferenced files which a retry can verify and adopt.
        commit_build(catalog, build, record, day, raw_sha, manifest, stage / "gold.csv")
        return "succeeded"
