"""NLDAS auto-publish adapter: Bronze S3 objects -> local medallion -> Silver/Gold artifacts."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from climate_platform.datasets.nldas import complete, paths, pipeline, references
from climate_platform.medallion.runner import medallion_lock
from climate_platform.modules.processing.auto_publish import (
    PublishResult,
    download_records,
    prune_cache,
    record_targets,
    safe_record_name,
    tree_artifacts,
)

_FILENAME = re.compile(r"^nldas_(fora|noah)0125_h\.a(\d{8})\.(\d{4}).*\.nc$", re.I)


def _record_path(root, filename):
    try:
        name = safe_record_name(filename)
    except ValueError:
        return None
    match = _FILENAME.fullmatch(name)
    if not match:
        return None
    product, day, _ = match.groups()
    return Path(root) / product.upper() / f"{day[:4]}-{day[4:6]}" / name


def sync_bronze(records, bronze_store, bronze_root, log=print):
    root = Path(bronze_root)

    def target_for(record):
        return _record_path(root, record.original_filename)

    counts = download_records(records, bronze_store, target_for, log=log)
    prune_cache(root, record_targets(records, bronze_store, target_for))
    return counts


def _product_details(report):
    return {
        name: {
            "bronze_hours": detail.get("bronze_hours"),
            "ready_weeks": detail.get("ready_weeks"),
            "built_silver": detail.get("built_silver"),
            "built_gold": detail.get("built_gold"),
        }
        for name, detail in report.details.get("products", {}).items()
    }


def _layer_artifacts(layer, root, products, key_prefix="source=nldas"):
    artifacts = []
    for product in products:
        artifacts.extend(
            tree_artifacts(layer, Path(root) / product, f"{key_prefix}/product={product}")
        )
    return artifacts


class NldasPublisher:
    source = "nldas"

    def __init__(self, product="both", references_dir=None, key_prefix="source=nldas"):
        self.product = product
        self.references_dir = references_dir
        self.key_prefix = key_prefix

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
        refs = Path(self.references_dir) if self.references_dir else paths.default_references()

        with medallion_lock(
            cache_root / "publish.lock", f"NLDAS publisher already running ({cache_root})"
        ):
            try:
                result.bronze_downloaded, result.bronze_cached = sync_bronze(
                    current, bronze_store, bronze_root, log
                )
            except Exception as exc:
                result.failures["bronze_sync"] = f"{type(exc).__name__}: {exc}"
                return [], result

            context = pipeline.default_context(
                self.product,
                bronze_root=bronze_root,
                references=refs,
                silver_root=silver_root,
                gold_root=gold_root,
                lock_file=cache_root / "medallion.lock",
            )
            try:
                run_report = pipeline.run(context, log)
            except Exception as exc:
                result.failures["pipeline"] = f"{type(exc).__name__}: {exc}"
                return [], result

            result.ready = run_report.ready
            result.reason = run_report.reason
            result.failures.update(run_report.failures)
            details = run_report.details.get("products", {})
            result.details = _product_details(run_report)
            if not run_report.ready:
                return [], result
            try:
                grid_size = references.reference_grid_size(refs)
                ready_by_product = {
                    name: {date.fromisoformat(day) for day in detail["ready_weeks"]}
                    for name, detail in details.items()
                }
                silver_products = [
                    name
                    for name, ready_days in ready_by_product.items()
                    if ready_days
                    & complete.silver_complete_weeks(silver_root, name, grid_size=grid_size)
                ]
                gold_products = [
                    name
                    for name, ready_days in ready_by_product.items()
                    if ready_days
                    & complete.gold_complete_weeks(gold_root, name, grid_size=grid_size)
                ]
            except Exception as exc:
                result.failures["complete"] = f"{type(exc).__name__}: {exc}"
                return [], result
            artifacts = _layer_artifacts("silver", silver_root, silver_products, self.key_prefix)
            artifacts += _layer_artifacts("gold", gold_root, gold_products, self.key_prefix)
            return artifacts, result
