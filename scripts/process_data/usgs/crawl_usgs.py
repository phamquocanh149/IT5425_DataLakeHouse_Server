"""USGS Bronze reference crawler (reference only — not part of the installable package).

One job: turn the USGS Water Data OGC API into the USGS Bronze layout the Server medallion
reads (station catalog, per-(site,year) normalized Parquet partitions, the raw page archive
and the checkpoint). This is the reference for how the Client obtains upstream data; the
Server main flow takes USGS Bronze from the Client and never crawls upstream itself.

The shared Bronze contract (``Config``/``Store``/``SCHEMA``/``job_path``/``errors``) lives in
``climate_platform.datasets.usgs`` so the crawler and the medallion agree on the layout.

Usage through the CLI (``scripts/process_data/usgs/run_usgs.py``):
    run_usgs.py discover
    run_usgs.py crawl --limit-sites 1
    run_usgs.py run
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import httpx
import pyarrow as pa
import pyarrow.parquet as pq

from climate_platform.common.clock import utc_now_iso
from climate_platform.datasets.usgs.bronze import SCHEMA
from climate_platform.datasets.usgs.errors import APIError, AuthError
from climate_platform.datasets.usgs.export import export
from climate_platform.datasets.usgs.paths import job_path
from climate_platform.datasets.usgs.preprocess import audit_raw, preprocess
from climate_platform.datasets.usgs.store import Store
from climate_platform.datasets.usgs.validate import validate
from climate_platform.medallion.io import write_json_atomic

BASE = "https://api.waterdata.usgs.gov/ogcapi/v1/collections/"


# --- USGS Water Data OGC API client -------------------------------------------------------


def safe_url(url):
    p = urlsplit(str(url))
    return urlunsplit(
        (
            p.scheme,
            p.netloc,
            p.path,
            urlencode(
                [
                    (k, v)
                    for k, v in parse_qsl(p.query)
                    if k.lower() not in {"api_key", "apikey", "token"}
                ]
            ),
            "",
        )
    )


class API:
    def __init__(self, config, transport=None, sleep=time.sleep):
        self.config = config
        key = os.environ.get("USGS_API_KEY")
        self.client = httpx.Client(
            timeout=90, transport=transport, headers={"X-Api-Key": key} if key else {}
        )
        self.sleep = sleep
        self.lock = threading.Lock()
        self.cooldown_path = Path(config.output) / "reports" / "rate_limit.json"
        self.retry_not_before = 0.0
        if self.cooldown_path.exists():
            saved = json.loads(self.cooldown_path.read_text())
            self.retry_not_before = float(saved.get("retry_not_before", 0))
            if not math.isfinite(self.retry_not_before):
                raise ValueError("Invalid stored rate-limit deadline")
        remaining = max(0, self.retry_not_before - time.time())
        self.next_request = time.monotonic() + remaining
        if remaining:
            print(
                f"USGS cooldown restored: waiting {math.ceil(remaining)}s before requests",
                file=sys.stderr,
                flush=True,
            )
        self.stop = threading.Event()

    def close(self):
        self.client.close()

    def throttle(self):
        with self.lock:
            delay = max(0, self.next_request - time.monotonic())
            self.sleep(delay)
            self.next_request = time.monotonic() + 1 / self.config.requests_per_second

    def get(self, url, params=None):
        url = safe_url(url)
        if urlsplit(url).scheme != "https" or urlsplit(url).netloc != "api.waterdata.usgs.gov":
            raise APIError("Refusing pagination outside USGS API origin")
        for attempt in range(self.config.retries + 1):
            if self.stop.is_set():
                raise AuthError("Run stopped after authentication failure")
            self.throttle()
            try:
                r = self.client.get(url, params=params)
            except httpx.TransportError:
                if attempt == self.config.retries:
                    raise APIError("Transport failure after retries") from None
                self.sleep(min(60, 2**attempt) + random.random())
                continue
            if r.status_code in (401, 403):
                self.stop.set()
                raise AuthError(f"Authentication failure: HTTP {r.status_code}")
            if r.status_code == 429 or r.status_code >= 500:
                if attempt == self.config.retries:
                    raise APIError(f"HTTP {r.status_code} after retries")
                delay = min(60, 2**attempt) + random.random()
                header = r.headers.get("Retry-After")
                if header:
                    try:
                        delay = max(delay, float(header))
                    except ValueError:
                        try:
                            delay = max(
                                delay,
                                (
                                    parsedate_to_datetime(header) - datetime.now(timezone.utc)
                                ).total_seconds(),
                            )
                        except (ValueError, TypeError):
                            pass
                print(
                    f"USGS HTTP {r.status_code}: retry {attempt + 1}/{self.config.retries} in {math.ceil(delay)}s",
                    file=sys.stderr,
                    flush=True,
                )
                with self.lock:
                    self.next_request = max(self.next_request, time.monotonic() + delay)
                    if r.status_code == 429:
                        self.retry_not_before = max(self.retry_not_before, time.time() + delay)
                        write_json_atomic(
                            self.cooldown_path,
                            {
                                "updated_at": utc_now_iso(),
                                "last_http_status": 429,
                                "retry_not_before": self.retry_not_before,
                                "resume_at_utc": datetime.fromtimestamp(
                                    self.retry_not_before, timezone.utc
                                ).isoformat(),
                                "rate_limit": r.headers.get("X-RateLimit-Limit"),
                                "rate_remaining": r.headers.get("X-RateLimit-Remaining"),
                            },
                        )
                self.sleep(delay)
                continue
            if r.status_code >= 400:
                raise APIError(f"Query failure: HTTP {r.status_code} at {safe_url(r.url)}")
            try:
                return r.json(), safe_url(r.url)
            except ValueError:
                raise APIError("USGS returned invalid JSON") from None
        raise APIError("Retry exhaustion")

    def pages(self, collection, params, archive):
        url = BASE + collection + "/items"
        query = {"f": "json", "limit": self.config.page_size, **params}
        seen = set()
        index = 0
        while url:
            body, request_url = self.get(url, query)
            if request_url in seen:
                raise APIError("Repeated pagination URL")
            seen.add(request_url)
            if not isinstance(body.get("features"), list):
                raise APIError("Missing features array")
            archive.mkdir(parents=True, exist_ok=True)
            body = json.loads(json.dumps(body))
            for link in body.get("links", []):
                if "href" in link:
                    link["href"] = safe_url(link["href"])
            payload = json.dumps(body, ensure_ascii=False).encode()
            path = archive / f"page-{index:06d}.json.gz"
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(gzip.compress(payload, mtime=0))
            tmp.replace(path)
            write_json_atomic(
                path.with_suffix(".meta.json"),
                {
                    "url": request_url,
                    "retrieved_at": utc_now_iso(),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "features": len(body["features"]),
                },
            )
            yield body["features"]
            next_links = [x["href"] for x in body.get("links", []) if x.get("rel") == "next"]
            if not body["features"] and next_links:
                raise APIError("Empty page with next link; completeness is ambiguous")
            url = urljoin(request_url, next_links[0]) if next_links else None
            query = None
            index += 1


# --- Bronze crawl -------------------------------------------------------------------------


def text_value(x):
    return x if isinstance(x, str) or x is None else json.dumps(x, ensure_ascii=False)


def discover(config, api):
    store = Store(config)
    root = store.root
    run = root / "raw" / "discovery" / str(time.time_ns())
    candidates = []
    for features in api.pages(
        "time-series-metadata",
        {
            "parameter_code": "00060",
            "statistic_id": "00003",
            "computation_period_identifier": "Daily",
        },
        run / "series",
    ):
        for f in features:
            p = f["properties"]
            if not str(p.get("monitoring_location_id", "")).startswith("USGS-"):
                continue
            candidates.append(p)
        print(f"Discovery: {len(candidates)} USGS series", flush=True)
    sites = {}
    wanted = sorted(
        {
            p["monitoring_location_id"]
            for p in candidates
            if (not p.get("begin") or p["begin"][:10] <= config.end)
            and (not p.get("end") or p["end"][:10] >= config.start)
        }
    )
    for offset in range(0, len(wanted), 100):
        batch = wanted[offset : offset + 100]
        if any(not s.removeprefix("USGS-").isdigit() for s in batch):
            raise APIError("Unexpected station identifier in metadata")
        expression = "id IN (" + ",".join("'" + s + "'" for s in batch) + ")"
        for features in api.pages(
            "monitoring-locations",
            {"filter": expression, "filter-lang": "cql2-text"},
            run / "locations" / str(offset),
        ):
            for f in features:
                p = f["properties"]
                sites[p["id"]] = (p, f.get("geometry"))
        if offset % 1000 == 0:
            print(f"Locations: {min(offset + 100, len(wanted))}/{len(wanted)}", flush=True)
    catalog = []
    for p in candidates:
        site = p["monitoring_location_id"]
        loc, geometry = sites.get(site, ({}, None))
        huc = str(loc.get("hydrologic_unit_code") or "")
        region = huc[:2]
        begin, end = (p.get("begin") or "")[:10], (p.get("end") or "")[:10]
        reason = "included"
        if begin and begin > config.end or end and end < config.start:
            reason = "outside_period"
        elif not huc or len(huc) < 2 or not huc.isdigit():
            reason = "missing_or_invalid_huc"
        elif region not in config.regions:
            reason = "outside_regions"
        row = {
            "site_id": site,
            "site_number": site.removeprefix("USGS-"),
            "name": loc.get("monitoring_location_name"),
            "huc": huc,
            "region": region,
            "coordinates": geometry.get("coordinates") if geometry else None,
            "time_series_id": p.get("id"),
            "unit": p.get("unit_of_measure"),
            "begin": begin or None,
            "end": end or None,
            "decision": reason,
        }
        catalog.append(row)
    write_json_atomic(root / "catalog.json", catalog)
    write_json_atomic(
        root / "discovery_manifest.json",
        {
            "created_at": utc_now_iso(),
            "config": asdict(config),
            "archive": str(run),
            "series": len(catalog),
            "included_sites": len({r["site_id"] for r in catalog if r["decision"] == "included"}),
            "decisions": {
                d: sum(r["decision"] == d for r in catalog)
                for d in sorted({r["decision"] for r in catalog})
            },
            "region_sites": {
                region: len(
                    {
                        r["site_id"]
                        for r in catalog
                        if r["region"] == region and r["decision"] == "included"
                    }
                )
                for region in config.regions
            },
        },
    )
    store.close()
    return catalog


def normalize(features, job):
    rows = {}
    for f in features:
        p = f["properties"]
        day = str(p.get("time", ""))[:10]
        date.fromisoformat(day)
        if (
            p.get("monitoring_location_id") != job["site"]
            or p.get("parameter_code") != "00060"
            or p.get("statistic_id") != "00003"
        ):
            raise APIError("Response violates station/parameter/statistic filter")
        if not job["start"] <= day <= job["end"]:
            raise APIError("Response contains an out-of-range date")
        raw = p.get("value")
        try:
            value = float(raw)
            if not math.isfinite(value):
                value = None
        except (TypeError, ValueError):
            value = None
        unit = p.get("unit_of_measure")
        unexpected = unit not in {"ft3/s", "ft^3/s", "ft3/s", "cfs"}
        oid = str(f.get("id") or "")
        if not oid:
            raise APIError("Observation has no ID")
        row = dict(
            observation_id=oid,
            site_id=job["site"],
            site_number=job["site"].removeprefix("USGS-"),
            date=day,
            discharge_cfs=None if unexpected else value,
            raw_value=text_value(raw),
            unit=unit,
            parameter_code="00060",
            statistic_id="00003",
            time_series_id=p.get("time_series_id") or p.get("timeseries_id"),
            approval_status=text_value(p.get("approval_status", p.get("approvals_status"))),
            qualifier=text_value(p.get("qualifier")),
            last_modified=p.get("last_modified"),
            region=job["region"],
            year=job["year"],
            invalid_numeric=value is None,
            unexpected_unit=unexpected,
            conflict=False,
        )
        if oid in rows and rows[oid] != row:
            raise APIError("Observation ID has inconsistent values across pages")
        rows[oid] = row
    groups = {}
    for row in rows.values():
        groups.setdefault(row["date"], []).append(row)
    for group in groups.values():
        values = {(x["raw_value"], x["unit"]) for x in group}
        if len(values) > 1:
            for row in group:
                row["conflict"] = True
    return sorted(rows.values(), key=lambda x: (x["date"], x["observation_id"]))


def download_job(config, api, job):
    started = time.monotonic()
    archive = (
        Path(config.output) / "raw" / "daily" / job["site"] / str(job["year"]) / str(time.time_ns())
    )
    features, pages = [], 0
    for batch in api.pages(
        "daily",
        {
            "monitoring_location_id": job["site"],
            "parameter_code": "00060",
            "statistic_id": "00003",
            "datetime": f"{job['start']}/{job['end']}",
        },
        archive,
    ):
        pages += 1
        features.extend(batch)
    rows = normalize(features, job)
    path = job_path(Path(config.output), job)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    pq.write_table(pa.Table.from_pylist(rows, schema=SCHEMA), tmp, compression="zstd")
    tmp.replace(path)
    return {
        "rows": len(rows),
        "pages": pages,
        "bytes": sum(p.stat().st_size for p in archive.glob("*.gz")),
        "elapsed": time.monotonic() - started,
    }


def choose_sites(catalog, limit=None):
    included = {r["site_id"]: r for r in catalog if r["decision"] == "included"}
    groups = {}
    for site, row in sorted(included.items()):
        groups.setdefault(row["region"], []).append(site)
    result = []
    for region in sorted(groups):
        result.append(groups[region].pop(0))
    if limit is not None:
        historical = sorted(
            {
                r["site_id"]
                for r in catalog
                if r["decision"] == "included"
                and r.get("end")
                and r["end"] < str(date.today().year) + "-01-01"
            }
        )
        for site in historical:
            if site not in result:
                result.append(site)
                break
    while any(groups.values()):
        for region in sorted(groups):
            if groups[region]:
                site = groups[region].pop(0)
                if site not in result:
                    result.append(site)
    return result if limit is None else result[:limit]


def crawl(config, api, limit=None, site_ids=None):
    store = Store(config)
    try:
        catalog = json.loads((store.root / "catalog.json").read_text())
        selected = choose_sites(catalog, limit)
        if site_ids:
            unknown = set(site_ids) - set(selected)
            if unknown:
                raise ValueError(
                    "Requested sites are absent or ineligible: " + ", ".join(sorted(unknown))
                )
            selected = [s for s in selected if s in site_ids]
        mapping = {r["site_id"]: r["region"] for r in catalog if r["decision"] == "included"}
        for site in selected:
            for year in range(int(config.start[:4]), int(config.end[:4]) + 1):
                start, end = max(config.start, f"{year}-01-01"), min(config.end, f"{year}-12-31")
                store.db.execute(
                    "INSERT OR IGNORE INTO jobs(site,year,region,start,end) VALUES (?,?,?,?,?)",
                    (site, year, mapping[site], start, end),
                )
        store.db.commit()
        jobs = [
            dict(r)
            for r in store.db.execute("SELECT * FROM jobs ORDER BY region,site,year")
            if r["site"] in selected and r["status"] not in {"complete", "empty"}
        ]
        auth_failure = None
        with ThreadPoolExecutor(max_workers=config.workers) as pool:
            pending = {}
            iterator = iter(jobs)

            def submit():
                job = next(iterator, None)
                if job is None or api.stop.is_set():
                    return False
                store.update(job["site"], job["year"], "running", error=None)
                pending[pool.submit(download_job, config, api, job)] = job
                return True

            for _ in range(config.workers):
                submit()
            while pending:
                future = next(as_completed(pending))
                job = pending.pop(future)
                try:
                    metrics = future.result()
                    status = "complete" if metrics["rows"] else "empty"
                    store.update(job["site"], job["year"], status, error=None, **metrics)
                    print(
                        f"{job['site']} {job['year']}: {status} ({metrics['rows']} rows)",
                        flush=True,
                    )
                except AuthError as exc:
                    auth_failure = exc
                    store.update(job["site"], job["year"], "error", error=str(exc))
                except Exception as exc:
                    message = str(exc) if isinstance(exc, APIError) else type(exc).__name__
                    store.update(job["site"], job["year"], "error", error=message)
                if not api.stop.is_set():
                    submit()
        write_json_atomic(
            store.root / "crawl_manifest.json",
            {
                "updated_at": utc_now_iso(),
                "config": asdict(config),
                "selected_sites": selected,
                "snapshot_note": "Historical values as supplied by USGS at retrieval time",
            },
        )
        if auth_failure:
            raise auth_failure
    finally:
        store.close()


# --- Full reference workflow --------------------------------------------------------------


def require_api_key():
    if not os.environ.get("USGS_API_KEY", "").strip():
        raise ValueError(
            "USGS_API_KEY is required before a full crawl. Configure it in the process environment; never put the key in logs or chat."
        )


def run_all(config, max_donors=20):
    path = Path(config.output) / "reports" / "workflow_status.json"
    state = {
        "started_at": utc_now_iso(),
        "status": "running",
        "stage": "validate_existing",
        "manual_comparison_completed": False,
    }
    write_json_atomic(path, state)
    try:
        report = validate(config)
        if not report["all_jobs_successful"]:
            state.update(stage="crawl", remaining_unplanned_jobs=report["unplanned_jobs"])
            write_json_atomic(path, state)
            require_api_key()
            api = API(config)
            try:
                crawl(config, api)
            finally:
                api.close()
        state["stage"] = "validate"
        write_json_atomic(path, state)
        report = validate(config)
        if not report["all_jobs_successful"]:
            raise ValueError(
                "Full crawl has unfinished jobs or validation errors. Rerun after addressing reports/quality.json."
            )
        state["stage"] = "audit_raw"
        write_json_atomic(path, state)
        if not audit_raw(config)["passed"]:
            raise ValueError("Raw archive verification failed. See reports/raw_audit.json.")
        state["stage"] = "export"
        write_json_atomic(path, state)
        export(config)
        state["stage"] = "preprocess"
        write_json_atomic(path, state)
        result = preprocess(config, max_donors)
        state.update(
            status="complete",
            stage="complete",
            completed_at=utc_now_iso(),
            preprocessing_output=str(result),
        )
        reference = Path(config.output) / "reports" / "manual_comparison.json"
        if reference.exists():
            state["manual_comparison_completed"] = bool(
                json.loads(reference.read_text()).get("passed")
            )
        write_json_atomic(path, state)
        return result
    except BaseException as exc:
        state.update(
            status="blocked" if isinstance(exc, ValueError) else "interrupted",
            stopped_at=utc_now_iso(),
            reason=str(exc) if isinstance(exc, ValueError) else type(exc).__name__,
        )
        write_json_atomic(path, state)
        raise
