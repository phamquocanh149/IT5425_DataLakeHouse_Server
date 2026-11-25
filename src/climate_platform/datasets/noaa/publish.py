"""NOAA auto-publish adapter: Bronze S3 snapshot files -> local medallion -> artifacts."""

from __future__ import annotations

import os
from pathlib import Path

from climate_platform.datasets.nldas import paths as nldas_paths
from climate_platform.datasets.noaa import bronze, pipeline, spec
from climate_platform.medallion.io import outputs_complete
from climate_platform.modules.processing.auto_publish import (
    PublishResult,
    download_records,
    prune_cache,
    record_targets,
    safe_record_name,
    tree_artifacts,
)


def _record_path(root, record):
    return (
        Path(root)
        / f"ingest_date={record.source_date}"
        / safe_record_name(record.original_filename)
    )


def sync_bronze(records, bronze_store, bronze_root, log=print):
    def target_for(record):
        return _record_path(bronze_root, record)

    counts = download_records(records, bronze_store, target_for, log=log)
    prune_cache(Path(bronze_root), record_targets(records, bronze_store, target_for))
    return counts


def _latest_complete_snapshot(bronze_root):
    folders = sorted(Path(bronze_root).glob("ingest_date=*"))
    for folder in reversed(folders):
        if bronze.is_snapshot_complete(folder):
            return folder
    return None


def _calendar_path(configured=None):
    if configured:
        return Path(configured)
    value = os.environ.get("NOAA_WEEK_DATES_CSV")
    if value:
        return Path(value)
    return nldas_paths.default_references() / "week_dates.csv"


class NoaaPublisher:
    source = "noaa"

    def __init__(self, key_prefix="source=noaa", week_dates_csv=None):
        self.key_prefix = key_prefix
        self.week_dates_csv = week_dates_csv

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
        bronze_root = cache_root / "bronze"
        silver_root = cache_root / "silver"
        gold_root = cache_root / "gold"
        cache_root.mkdir(parents=True, exist_ok=True)
        calendar = _calendar_path(self.week_dates_csv)

        try:
            result.bronze_downloaded, result.bronze_cached = sync_bronze(
                current, bronze_store, bronze_root, log
            )
        except Exception as exc:
            result.failures["bronze_sync"] = f"{type(exc).__name__}: {exc}"
            return [], result

        snapshot = _latest_complete_snapshot(bronze_root)
        if snapshot is None:
            result.reason = "no complete NOAA snapshot in Bronze (need _manifest.json and 4 files)"
            return [], result

        context = pipeline.default_context(
            bronze_root=bronze_root,
            silver_root=silver_root,
            gold_root=gold_root,
            week_dates_csv=calendar,
            snapshot_dir=snapshot,
            lock_file=cache_root / "noaa.lock",
        )
        try:
            report = pipeline.run(context, log)
        except Exception as exc:
            result.failures["pipeline"] = f"{type(exc).__name__}: {exc}"
            return [], result
        result.ready = report.ready
        result.reason = report.reason
        if report.details.get("calendar_ok") is False:
            note = "Gold skipped: missing NOAA week calendar (week_dates.csv)"
            result.reason = f"{report.reason}; {note}" if report.reason else note
        result.failures.update(report.failures)
        result.details = {"snapshot": str(snapshot), **report.details}

        artifacts = []
        if outputs_complete(silver_root, spec.COMPLETE_MARKER, spec.SILVER_OUTPUTS):
            artifacts += tree_artifacts("silver", silver_root, self.key_prefix)
        if outputs_complete(gold_root, spec.COMPLETE_MARKER, spec.GOLD_OUTPUTS):
            artifacts += tree_artifacts("gold", gold_root, self.key_prefix)
        return artifacts, result
