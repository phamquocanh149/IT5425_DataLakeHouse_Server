"""Station daily QC and spatial donor discovery; never imputes discharge."""

from __future__ import annotations

import heapq
import json
import math
import sqlite3
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from climate_platform.common.clock import utc_now_iso
from climate_platform.datasets.usgs.daily import clean_day, metadata
from climate_platform.datasets.usgs.paths import job_path
from climate_platform.datasets.usgs.store import Store
from climate_platform.datasets.usgs.validate import validate
from climate_platform.medallion.io import file_hash, write_json_atomic

# One checksum helper shared with the medallion layers.
sha256 = file_hash

DAILY = pa.schema(
    [
        ("site_id", pa.string()),
        ("date", pa.string()),
        ("discharge_cfs", pa.float64()),
        ("qc_flags", pa.list_(pa.string())),
        ("source_observation_ids", pa.list_(pa.string())),
        ("approval_status", pa.list_(pa.string())),
        ("qualifier", pa.list_(pa.string())),
    ]
)
CANDIDATE = pa.schema(
    [
        ("target_site_id", pa.string()),
        ("date", pa.string()),
        ("huc_level", pa.int32()),
        ("huc", pa.string()),
        ("donor_site_id", pa.string()),
        ("discharge_cfs", pa.float64()),
        ("distance_km", pa.float64()),
        ("rank", pa.int32()),
        ("source_observation_ids", pa.list_(pa.string())),
    ]
)
SUMMARY = pa.schema(
    [
        ("target_site_id", pa.string()),
        ("date", pa.string()),
        ("huc_level", pa.int32()),
        ("huc", pa.string()),
        ("eligible_count", pa.int32()),
        ("retained_count", pa.int32()),
        ("reason", pa.string()),
    ]
)


def haversine(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, [*a, *b])
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 6371.0088 * 2 * math.asin(math.sqrt(min(1, max(0, h))))


class BufferedWriter:
    def __init__(self, path, schema):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.writer = pq.ParquetWriter(path, schema, compression="zstd")
        self.schema, self.rows, self.count = schema, [], 0

    def add(self, row):
        self.rows.append(row)
        self.count += 1
        if len(self.rows) >= 5000:
            self.flush()

    def flush(self):
        if self.rows:
            self.writer.write_table(pa.Table.from_pylist(self.rows, schema=self.schema))
            self.rows.clear()

    def close(self):
        self.flush()
        self.writer.close()


def require_complete(config):
    report = validate(config)
    if not report["all_jobs_successful"]:
        raise ValueError(
            f"Preprocessing blocked: crawl/validation incomplete; {report['unplanned_jobs']} unplanned jobs, {len(report['unresolved_jobs'])} unresolved jobs. See reports/quality.json"
        )
    return report


def audit_raw(config):
    root = Path(config.output)
    checked, issues = 0, []
    for path in sorted((root / "raw").rglob("*.json.gz")):
        sidecar = path.with_suffix(".meta.json")
        try:
            meta = json.loads(sidecar.read_text())
            if sha256(path) != meta["sha256"]:
                raise ValueError("Checksum mismatch")
            checked += 1
        except (OSError, ValueError, KeyError) as exc:
            issues.append({"path": str(path), "error": str(exc)})
    if checked == 0:
        issues.append({"error": "No archived raw responses found"})
    store = Store(config)
    try:
        for job in store.db.execute("SELECT * FROM jobs WHERE status IN ('complete','empty')"):
            archive = root / "raw" / "daily" / job["site"] / str(job["year"])
            attempts = sorted(archive.glob("*")) if archive.exists() else []
            if not any(
                len(list(attempt.glob("*.json.gz"))) == job["pages"] and job["pages"] > 0
                for attempt in attempts
            ):
                issues.append(
                    {
                        "site_id": job["site"],
                        "year": job["year"],
                        "error": "Missing complete raw page archive",
                    }
                )
    finally:
        store.close()
    result = {
        "checked_at": utc_now_iso(),
        "checked_files": checked,
        "issues": issues,
        "passed": not issues,
    }
    write_json_atomic(root / "reports" / "raw_audit.json", result)
    return result


def preprocess(config, max_donors=20):
    if max_donors < 1:
        raise ValueError("max_donors must be positive")
    report = require_complete(config)
    if not audit_raw(config)["passed"]:
        raise ValueError("Raw archive verification failed. See reports/raw_audit.json.")
    root = Path(config.output)
    catalog_path = root / "catalog.json"
    catalog = json.loads(catalog_path.read_text())
    sites = {r["site_id"] for r in catalog if r["decision"] == "included"}
    meta, metadata_issues = metadata(catalog, sites)
    run = root / "preprocessed" / str(time.time_ns())
    run.mkdir(parents=True)
    manifest = {
        "created_at": utc_now_iso(),
        "status": "running",
        "config": asdict(config),
        "max_donors": max_donors,
        "catalog_sha256": sha256(catalog_path),
        "method": "Station HUC4/6/8 donor search; no imputation",
        "sources": [],
        "manual_comparison_completed": False,
    }
    manual = root / "reports" / "manual_comparison.json"
    if manual.exists():
        manifest["manual_comparison_completed"] = bool(json.loads(manual.read_text()).get("passed"))
    write_json_atomic(run / "manifest.json", manifest)
    store = Store(config)
    stage = sqlite3.connect(run / "working.sqlite")
    stage.execute(
        "CREATE TABLE daily(site TEXT, date TEXT, value REAL, ids TEXT, PRIMARY KEY(date,site))"
    )
    counts = Counter()
    try:
        for j in store.db.execute("SELECT * FROM jobs ORDER BY year,site"):
            path = job_path(root, j)
            manifest["sources"].append({"path": str(path), "sha256": sha256(path)})
            groups = defaultdict(list)
            for row in pq.ParquetFile(path).read().to_pylist():
                groups[row["date"]].append(row)
            cleaned = []
            for ordinal in range(
                date.fromisoformat(j["start"]).toordinal(),
                date.fromisoformat(j["end"]).toordinal() + 1,
            ):
                day = date.fromordinal(ordinal).isoformat()
                row = clean_day(j["site"], day, groups.get(day, []))
                cleaned.append(row)
                counts["daily_rows"] += 1
                counts["usable_days" if row["discharge_cfs"] is not None else "unusable_days"] += 1
                counts.update(row["qc_flags"])
            out = (
                run
                / "daily"
                / f"region={j['region']}"
                / f"year={j['year']}"
                / f"{j['site']}.parquet"
            )
            out.parent.mkdir(parents=True, exist_ok=True)
            pq.write_table(pa.Table.from_pylist(cleaned, schema=DAILY), out, compression="zstd")
            stage.executemany(
                "INSERT INTO daily VALUES (?,?,?,?)",
                [
                    (
                        r["site_id"],
                        r["date"],
                        r["discharge_cfs"],
                        json.dumps(r["source_observation_ids"]),
                    )
                    for r in cleaned
                ],
            )
            stage.commit()
        for year in range(int(config.start[:4]), int(config.end[:4]) + 1):
            writers = [
                BufferedWriter(run / folder / f"year={year}" / "part.parquet", schema)
                for folder, schema in [("candidates", CANDIDATE), ("candidate_summary", SUMMARY)]
            ]
            cw, sw = writers
            try:
                start, end = max(config.start, f"{year}-01-01"), min(config.end, f"{year}-12-31")
                for ordinal in range(
                    date.fromisoformat(start).toordinal(), date.fromisoformat(end).toordinal() + 1
                ):
                    day = date.fromordinal(ordinal).isoformat()
                    entries = list(
                        stage.execute(
                            "SELECT site,value,ids FROM daily WHERE date=? ORDER BY site", (day,)
                        )
                    )
                    available = defaultdict(list)
                    for site, value, ids in entries:
                        if value is not None and meta[site]["coordinates"] is not None:
                            for level, code in meta[site]["hucs"].items():
                                if code:
                                    available[(level, code)].append((site, value, ids))
                    for target, value, _ in entries:
                        if value is not None:
                            continue
                        for level, code in meta[target]["hucs"].items():
                            xy = meta[target]["coordinates"]
                            pool = (
                                available.get((level, code), []) if code and xy is not None else []
                            )
                            # Target is missing, so it cannot be in the valid donor pool.
                            ranked = heapq.nsmallest(
                                max_donors,
                                (
                                    (haversine(xy, meta[s]["coordinates"]), s, v, ids)
                                    for s, v, ids in pool
                                ),
                                key=lambda item: (item[0], item[1]),
                            )
                            reason = (
                                "missing_huc"
                                if not code
                                else "missing_coordinates"
                                if xy is None
                                else "no_valid_donors"
                                if not pool
                                else "ok"
                            )
                            sw.add(
                                {
                                    "target_site_id": target,
                                    "date": day,
                                    "huc_level": level,
                                    "huc": code,
                                    "eligible_count": len(pool),
                                    "retained_count": len(ranked),
                                    "reason": reason,
                                }
                            )
                            for rank, (distance, donor, v, ids) in enumerate(ranked, 1):
                                cw.add(
                                    {
                                        "target_site_id": target,
                                        "date": day,
                                        "huc_level": level,
                                        "huc": code,
                                        "donor_site_id": donor,
                                        "discharge_cfs": v,
                                        "distance_km": distance,
                                        "rank": rank,
                                        "source_observation_ids": json.loads(ids),
                                    }
                                )
                            counts["candidate_rows"] += len(ranked)
                            counts["summary_rows"] += 1
                            counts[f"summary_{reason}"] += 1
            finally:
                for writer in writers:
                    writer.close()
            print(f"Preprocessing {year}: completed", flush=True)
        write_json_atomic(
            run / "report.json",
            {
                "created_at": utc_now_iso(),
                "sites": len(sites),
                "counts": dict(counts),
                "metadata_issues": metadata_issues,
                "crawl_status_counts": report["status_counts"],
                "filled_values": 0,
                "note": "Donors are observed values on the same date. No percentile calculation or imputation.",
            },
        )
        manifest.update(status="complete", completed_at=utc_now_iso())
        write_json_atomic(run / "manifest.json", manifest)
        return run
    except BaseException:
        manifest.update(status="incomplete", stopped_at=utc_now_iso())
        write_json_atomic(run / "manifest.json", manifest)
        raise
    finally:
        stage.close()
        store.close()
        (run / "working.sqlite").unlink(missing_ok=True)
