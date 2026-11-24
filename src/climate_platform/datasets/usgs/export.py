"""USGS Bronze export and manual comparison.

One job: turn the normalized Bronze partitions into per-station CSVs and cross-check a
user-downloaded reference CSV. It writes only export artifacts.
"""

from __future__ import annotations

import csv
import hashlib
import math
from pathlib import Path

import pyarrow.parquet as pq

from climate_platform.common.clock import utc_now_iso
from climate_platform.datasets.usgs.bronze import SCHEMA
from climate_platform.datasets.usgs.paths import job_path
from climate_platform.datasets.usgs.store import Store
from climate_platform.medallion.io import write_json_atomic


def export(config):
    store = Store(config)
    try:
        folder = store.root / "csv"
        folder.mkdir(exist_ok=True)
        sites = [r[0] for r in store.db.execute("SELECT DISTINCT site FROM jobs ORDER BY site")]
        files = []
        for site in sites:
            jobs = [
                dict(r)
                for r in store.db.execute(
                    "SELECT * FROM jobs WHERE site=? AND status IN ('complete','empty') ORDER BY year",
                    (site,),
                )
            ]
            path = folder / f"{site}.csv"
            with path.with_suffix(".tmp").open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=SCHEMA.names)
                writer.writeheader()
                for job in jobs:
                    writer.writerows(pq.ParquetFile(job_path(store.root, job)).read().to_pylist())
            path.with_suffix(".tmp").replace(path)
            files.append(str(path))
        write_json_atomic(
            store.root / "export_manifest.json",
            {
                "created_at": utc_now_iso(),
                "csv_files": files,
                "warning": "Read quality.json for incomplete jobs; site IDs must be imported as text.",
            },
        )
        return files
    finally:
        store.close()


def compare(config, reference):
    """Compare user-downloaded CSV: site_id,date,discharge_cfs (minimum 5 sites)."""
    with open(reference, newline="", encoding="utf-8-sig") as f:
        refs = list(csv.DictReader(f))
    if not refs or not {"site_id", "date", "discharge_cfs"} <= set(refs[0]):
        raise ValueError("Reference needs site_id,date,discharge_cfs columns")
    sites = {r["site_id"] for r in refs}
    if len(sites) < 5:
        raise ValueError("Manual cross-check requires at least five stations")
    store = Store(config)
    mismatches = []
    try:
        for site in sites:
            observations = {}
            for job in store.db.execute(
                "SELECT * FROM jobs WHERE site=? AND status IN ('complete','empty')", (site,)
            ):
                for r in pq.ParquetFile(job_path(store.root, job)).read().to_pylist():
                    observations.setdefault(r["date"], set()).add(r["discharge_cfs"])
            for ref in (r for r in refs if r["site_id"] == site):
                expected = float(ref["discharge_cfs"])
                actual = observations.get(ref["date"], set())
                if not any(
                    v is not None and math.isclose(v, expected, rel_tol=1e-9, abs_tol=1e-9)
                    for v in actual
                ):
                    mismatches.append({**ref, "actual": list(actual)})
        result = {
            "checked_at": utc_now_iso(),
            "reference": str(reference),
            "reference_sha256": hashlib.sha256(Path(reference).read_bytes()).hexdigest(),
            "sites": len(sites),
            "rows": len(refs),
            "mismatches": mismatches,
            "passed": not mismatches,
        }
        write_json_atomic(store.root / "reports" / "manual_comparison.json", result)
        return result
    finally:
        store.close()
