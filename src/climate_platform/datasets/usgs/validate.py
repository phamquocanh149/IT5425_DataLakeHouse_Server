"""USGS Bronze validation.

One job: read the client-provided Bronze checkpoint + normalized Parquet and produce the
quality report that decides whether the Bronze is complete enough for the medallion to run.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date

import pyarrow as pa
import pyarrow.parquet as pq

from climate_platform.common.clock import utc_now_iso
from climate_platform.datasets.usgs.paths import job_path
from climate_platform.datasets.usgs.store import Store
from climate_platform.medallion.io import write_json_atomic


def validate(config):
    store = Store(config)
    station_stats, errors, region_stats = {}, [], {}
    try:
        jobs = [dict(r) for r in store.db.execute("SELECT * FROM jobs ORDER BY site,year")]
        for job in jobs:
            site = job["site"]
            stat = station_stats.setdefault(
                site,
                {
                    "site_id": site,
                    "region": job["region"],
                    "observed_days": 0,
                    "numeric_days": 0,
                    "expected_days": 0,
                    "conflict_rows": 0,
                    "invalid_numeric_rows": 0,
                    "unexpected_unit_rows": 0,
                    "years": [],
                },
            )
            expected = (date.fromisoformat(job["end"]) - date.fromisoformat(job["start"])).days + 1
            stat["expected_days"] += expected
            ys = {
                "year": job["year"],
                "status": job["status"],
                "expected_days": expected,
                "observed_days": 0,
                "missing_ranges": [],
                "rows": 0,
            }
            if job["status"] not in {"complete", "empty"}:
                errors.append(
                    {
                        "site_id": site,
                        "year": job["year"],
                        "status": job["status"],
                        "error": job["error"],
                    }
                )
            else:
                try:
                    rows = pq.ParquetFile(job_path(store.root, job)).read().to_pylist()
                    ids = [r["observation_id"] for r in rows]
                    if len(set(ids)) != len(ids) or len(rows) != job["rows"]:
                        raise ValueError("Duplicate IDs or checkpoint row count mismatch")
                    if (job["status"] == "empty") != (len(rows) == 0):
                        raise ValueError("Job status inconsistent with row count")
                    for row in rows:
                        date.fromisoformat(row["date"])
                        if (
                            row["site_id"] != site
                            or not job["start"] <= row["date"] <= job["end"]
                            or row["parameter_code"] != "00060"
                            or row["statistic_id"] != "00003"
                        ):
                            raise ValueError("Row violates scope")
                    days = {r["date"] for r in rows}
                    numeric = {r["date"] for r in rows if r["discharge_cfs"] is not None}
                    ys.update(rows=len(rows), observed_days=len(days), numeric_days=len(numeric))
                    stat["observed_days"] += len(days)
                    stat["numeric_days"] += len(numeric)
                    for flag in ("conflict", "invalid_numeric", "unexpected_unit"):
                        stat[flag + "_rows"] += sum(r[flag] for r in rows)
                    start_ord, end_ord = (
                        date.fromisoformat(job["start"]).toordinal(),
                        date.fromisoformat(job["end"]).toordinal(),
                    )
                    gap = None
                    for ordinal in range(start_ord, end_ord + 2):
                        missing = (
                            ordinal <= end_ord and date.fromordinal(ordinal).isoformat() not in days
                        )
                        if missing and gap is None:
                            gap = ordinal
                        elif not missing and gap is not None:
                            ys["missing_ranges"].append(
                                [
                                    date.fromordinal(gap).isoformat(),
                                    date.fromordinal(ordinal - 1).isoformat(),
                                ]
                            )
                            gap = None
                except (OSError, ValueError, pa.ArrowException) as exc:
                    errors.append({"site_id": site, "year": job["year"], "error": str(exc)})
            stat["years"].append(ys)
        year_stats = {}
        for stat in station_stats.values():
            for ys in stat["years"]:
                group = year_stats.setdefault(
                    str(ys["year"]), {"sites": 0, "rows": 0, "observed_days": 0, "expected_days": 0}
                )
                group["sites"] += 1
                for field in ("rows", "observed_days", "expected_days"):
                    group[field] += ys[field]
            stat["missing_days"] = stat["expected_days"] - stat["observed_days"]
            stat["coverage"] = stat["observed_days"] / stat["expected_days"]
            region = region_stats.setdefault(
                stat["region"], {"sites": 0, "observed_days": 0, "expected_days": 0}
            )
            region["sites"] += 1
            region["observed_days"] += stat["observed_days"]
            region["expected_days"] += stat["expected_days"]
        catalog = (
            json.loads((store.root / "catalog.json").read_text())
            if (store.root / "catalog.json").exists()
            else []
        )
        eligible = {r["site_id"] for r in catalog if r["decision"] == "included"}
        expected = {
            (site, year)
            for site in eligible
            for year in range(int(config.start[:4]), int(config.end[:4]) + 1)
        }
        actual = {(j["site"], j["year"]) for j in jobs}
        planned = len(expected)
        regions = {r["site_id"]: r["region"] for r in catalog if r["decision"] == "included"}
        for job in jobs:
            key = (job["site"], job["year"])
            if (
                key not in expected
                or job["region"] != regions.get(job["site"])
                or job["start"] != max(config.start, f"{job['year']}-01-01")
                or job["end"] != min(config.end, f"{job['year']}-12-31")
            ):
                errors.append(
                    {
                        "site_id": job["site"],
                        "year": job["year"],
                        "error": "Job differs from catalog/date/region scope",
                    }
                )
        report = {
            "created_at": utc_now_iso(),
            "scope": asdict(config),
            "stations": list(station_stats.values()),
            "regions": region_stats,
            "years": year_stats,
            "unresolved_jobs": errors,
            "eligible_sites": len(eligible),
            "pilot_characteristics": {
                "regions": sorted(region_stats),
                "full_coverage_sites": [
                    s["site_id"] for s in station_stats.values() if s["coverage"] == 1
                ],
                "gapped_sites": [
                    s["site_id"] for s in station_stats.values() if 0 < s["coverage"] < 1
                ],
                "historically_ended_series_sites": sorted(
                    {
                        r["site_id"]
                        for r in catalog
                        if r["site_id"] in station_stats
                        and r.get("end")
                        and r["end"] < str(date.today().year) + "-01-01"
                    }
                ),
            },
            "unplanned_jobs": len(expected - actual),
            "unexpected_jobs": len(actual - expected),
            "total_jobs": len(jobs),
            "all_jobs_successful": bool(expected) and not errors and expected == actual,
            "status_counts": {
                s: sum(j["status"] == s for j in jobs)
                for s in ("pending", "running", "complete", "empty", "error")
            },
            "metrics": {
                "elapsed_worker_seconds": sum(j["elapsed"] or 0 for j in jobs),
                "pages": sum(j["pages"] for j in jobs),
                "raw_bytes": sum(j["bytes"] for j in jobs),
            },
            "note": "Missing days are not filled. Expected days cover requested calendar scope, not station operating lifetime.",
        }
        successful = [j for j in jobs if j["status"] in {"complete", "empty"}]
        remaining = max(0, planned - len(successful))
        if successful:
            average_elapsed = sum(j["elapsed"] or 0 for j in successful) / len(successful)
            average_pages = sum(j["pages"] for j in successful) / len(successful)
            report["estimate"] = {
                "remaining_jobs": remaining,
                "remaining_raw_bytes": round(
                    remaining * sum(j["bytes"] for j in successful) / len(successful)
                ),
                "ideal_remaining_wall_seconds": round(
                    max(
                        remaining * average_elapsed / config.workers,
                        remaining * average_pages / config.requests_per_second,
                    )
                ),
                "note": "Pilot extrapolation only; excludes future rate-limit waits, retries and changes in station density.",
            }
        write_json_atomic(store.root / "reports" / "quality.json", report)
        write_json_atomic(store.root / "reports" / "unresolved_jobs.json", errors)
        return report
    finally:
        store.close()
