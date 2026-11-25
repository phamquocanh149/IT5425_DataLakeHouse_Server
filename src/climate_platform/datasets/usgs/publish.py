"""USGS auto-publish adapter: uploaded crawl workspace -> medallion -> artifacts."""

from __future__ import annotations

import json
import os
import shutil
import zipfile
from pathlib import Path

from climate_platform.modules.processing import auto_publish
from climate_platform.modules.processing.auto_publish import (
    PublishResult,
    download_records,
    prune_cache,
    record_targets,
    safe_record_name,
    tree_artifacts,
)

_EXTRACTION_STATE = ".extraction.json"


def _safe_member(name):
    return auto_publish.safe_archive_parts(name)


def _extract(archive, target):
    target = Path(target).resolve()
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        auto_publish.check_archive_limits(members)
        total = 0
        for member in members:
            relative = _safe_member(member.filename)
            destination = target.joinpath(*relative)
            if not destination.resolve().is_relative_to(target):
                raise ValueError("USGS archive member escapes the Bronze root")
            if member.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            total += auto_publish.extract_member_limited(
                bundle,
                member,
                destination,
                max_bytes=auto_publish.MAX_ARCHIVE_UNCOMPRESSED_BYTES - total,
            )


def _target_for(uploads, bronze_root, record):
    name = safe_record_name(record.original_filename)
    if name.lower().endswith(".zip"):
        return Path(uploads) / name
    return Path(bronze_root) / name


def _zip_records(records):
    """Newest record per archive name; a stale duplicate must not win."""
    latest = {}
    for record in sorted(records, key=auto_publish.record_order):
        if record.original_filename.lower().endswith(".zip"):
            latest[safe_record_name(record.original_filename)] = record
    return latest


def _zip_state(records):
    return {name: record.sha256 for name, record in _zip_records(records).items()}


def _write_state(path, state):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


class UsgsPublisher:
    source = "usgs"

    def __init__(self, key_prefix="source=usgs", start=None, end=None):
        self.key_prefix = key_prefix
        self.start = start or os.environ.get("USGS_START", "2020-01-01")
        self.end = end or os.environ.get("USGS_END", "2022-12-31")

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
        bronze_root = cache_root / "bronze"
        silver_root = cache_root / "silver"
        gold_root = cache_root / "gold"
        cache_root.mkdir(parents=True, exist_ok=True)

        def target_for(record):
            return _target_for(uploads, bronze_root, record)

        try:
            result.bronze_downloaded, result.bronze_cached = download_records(
                current, bronze_store, target_for, log=log
            )
            state_file = uploads / _EXTRACTION_STATE
            targets = record_targets(current, bronze_store, target_for)
            markers = [
                uploads / (target.name + ".extracted")
                for target in targets
                if target.name.lower().endswith(".zip")
            ]
            prune_cache(uploads, targets, extra=[state_file, *markers])
            state = _zip_state(current)
            previous = {}
            if state_file.is_file():
                try:
                    previous = json.loads(state_file.read_text(encoding="utf-8"))
                except ValueError:
                    previous = {}
            if state != previous or (not state_file.is_file() and not state):
                if bronze_root.is_symlink():
                    bronze_root.unlink()
                elif bronze_root.exists():
                    shutil.rmtree(bronze_root)
                for marker in uploads.glob("*.extracted"):
                    marker.unlink()
            for name, record in _zip_records(current).items():
                archive = uploads / name
                marker = uploads / (name + ".extracted")
                if marker.is_file() and marker.read_text(encoding="ascii").strip() == record.sha256:
                    continue
                _extract(archive, bronze_root)
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.write_text(record.sha256 + "\n", encoding="ascii")
            _write_state(state_file, state)
        except Exception as exc:
            result.failures["bronze_layout"] = f"{type(exc).__name__}: {exc}"
            return [], result

        if not (bronze_root / "checkpoint.sqlite").is_file():
            result.reason = (
                "no USGS crawl workspace in Bronze (need checkpoint.sqlite + catalog.json)"
            )
            return [], result

        from climate_platform.datasets.usgs import pipeline as usgs_pipeline
        from climate_platform.datasets.usgs.config import Config

        grid = os.environ.get("USGS_GRID") or str(bronze_root / "grid_huc_inputs" / "grid.csv")
        wbd = os.environ.get("USGS_WBD") or str(
            bronze_root / "grid_huc_inputs" / "wbd" / "WBDHU8.gpkg"
        )
        if not Path(grid).is_file() or not Path(wbd).is_file():
            result.reason = "missing USGS grid/WBD inputs (set USGS_GRID and USGS_WBD)"
            return [], result
        cfg = Config(
            start=self.start,
            end=self.end,
            output=str(bronze_root),
            silver_root=str(silver_root),
            gold_root=str(gold_root),
        ).check()
        try:
            report = usgs_pipeline.run(cfg, grid, wbd, log=log)
        except Exception as exc:
            result.failures["pipeline"] = f"{type(exc).__name__}: {exc}"
            return [], result
        result.ready = report.ready
        result.reason = report.reason
        result.failures.update(report.failures)
        result.details = report.details

        artifacts = []
        if usgs_pipeline._completed_runs(silver_root, "silver"):
            artifacts += tree_artifacts("silver", silver_root, self.key_prefix)
        if usgs_pipeline._completed_runs(gold_root, "gold"):
            artifacts += tree_artifacts("gold", gold_root, self.key_prefix)
        return artifacts, result
