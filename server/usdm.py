"""Offline USDM replay and Medallion orchestration on the existing Bronze registry."""

import csv
import hashlib
import json
import logging
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import zipfile
from contextlib import closing, contextmanager
from datetime import date, datetime, timezone
from pathlib import Path

from server.config import settings
from server.metadata import MetadataManager, file_hash

logger = logging.getLogger("climate_server.usdm")
DATASET_KEY = "usdm/gis/CONUS/M/weekly"
WORKER = Path(__file__).with_name("usdm_worker.py")


@contextmanager
def exclusive_run(root):
    """OS lock releases even on process death; an abandoned file is not a stale lock."""
    with (root / "pipeline.lock").open("a+b") as stream:
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            if not stream.read(1):
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


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


def run_worker(python, args):
    result = subprocess.run(
        [str(python), str(WORKER), *map(str, args)], capture_output=True, timeout=600
    )
    if result.returncode:
        # Worker diagnostics retained locally, not emitted as potentially sensitive payload logs.
        raise ValueError(
            "GIS worker failed: " + result.stderr.decode("utf-8", errors="replace")[-3000:]
        )


def initialize_catalog(path):
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS builds (
                build_id TEXT PRIMARY KEY, file_id TEXT NOT NULL, source_date TEXT NOT NULL,
                revision INTEGER NOT NULL, raw_sha256 TEXT NOT NULL,
                manifest TEXT NOT NULL, completed_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS attempts (
                attempt_id INTEGER PRIMARY KEY, source_date TEXT NOT NULL,
                status TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS gold_cells (
                build_id TEXT NOT NULL REFERENCES builds(build_id),
                time TEXT NOT NULL, grid TEXT NOT NULL, lon REAL NOT NULL, lat REAL NOT NULL,
                drought TEXT NOT NULL CHECK(drought IN ('0','D0','D1','D2','D3','D4')),
                PRIMARY KEY(build_id,grid));
            CREATE VIEW IF NOT EXISTS gold_weekly AS
                SELECT build_id,time,drought,count(*) AS cell_count
                FROM gold_cells GROUP BY build_id,time,drought;
        """)


def verify_products(root, manifest):
    for product in manifest["products"].values():
        path = root / product["path"]
        path.resolve().relative_to(root.resolve())
        if not path.is_file() or file_hash(path) != product["sha256"]:
            raise ValueError("Published product requires reconciliation")


def materialize_raw(manager, record, target):
    if record.s3_object_key:
        from server.storage import S3Storage

        storage = S3Storage()
        try:
            kwargs = {"Bucket": record.s3_bucket, "Key": record.s3_object_key}
            if record.s3_version_id:
                kwargs["VersionId"] = record.s3_version_id
            response = storage.client.get_object(**kwargs)
            with response["Body"] as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
        finally:
            storage.client.close()
    else:
        shutil.copyfile(manager.resolve_raw(record.stored_path), target)
    if target.stat().st_size != record.size_bytes or file_hash(target) != record.sha256:
        raise ValueError("Bronze checksum mismatch")


def run_pipeline(source, root, python, start=None, end=None):
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
        return _run(source, root, python, weeks)


def _run(source, root, python, weeks):
    manager = MetadataManager()
    manager.initialize()
    catalog = root / "warehouse.sqlite3"
    initialize_catalog(catalog)
    report = {"succeeded": 0, "skipped": 0, "failed": 0, "weeks": []}
    with tempfile.TemporaryDirectory(dir=root, prefix="work-") as directory:
        work = Path(directory)
        cleaner = work / "cleaner.py"
        cleaner_source = source / "silver/scripts/usdm_bronze_to_silver.py"
        if not cleaner_source.exists():
            cleaner_source = (
                Path(__file__).resolve().parents[1] / "vendor/usdm/usdm_bronze_to_silver.py"
            )
        shutil.copyfile(cleaner_source, cleaner)
        grid = work / "grid.csv"
        run_worker(python, ["--grid-source", source / "gold/data/usdmfinal.csv", "--grid", grid])
        recipe = {
            "cleaner": file_hash(cleaner),
            "worker": file_hash(WORKER),
            "grid": file_hash(grid),
            "version": 1,
            "libraries": json.loads(grid.with_suffix(".versions.json").read_text(encoding="utf-8")),
        }
        # Preserve the exact executable recipe for every new historical build.
        recipes = root / "recipes"
        recipes.mkdir(exist_ok=True)
        for source_file, expected in ((cleaner, recipe["cleaner"]), (WORKER, recipe["worker"])):
            if file_hash(source_file) != expected:
                raise ValueError("Recipe changed during snapshot")
            destination = recipes / (expected + ".py")
            if destination.exists():
                if file_hash(destination) != expected:
                    raise ValueError("Archived recipe checksum mismatch")
            else:
                with destination.open("xb") as out, source_file.open("rb") as inp:
                    shutil.copyfileobj(inp, out)
                    out.flush()
                    os.fsync(out.fileno())
                if file_hash(destination) != expected:
                    raise ValueError("Recipe changed during snapshot")
        for day, shp in weeks.items():
            try:
                status = process_week(
                    manager, catalog, root, work, python, cleaner, grid, recipe, day, shp
                )
                report[status] += 1
                detail = ""
                logger.info("usdm week=%s status=%s", day, status)
            except Exception as exc:
                status, detail = "failed", str(exc)
                report["failed"] += 1
                logger.error("usdm week=%s status=failed error_type=%s", day, type(exc).__name__)
            with closing(sqlite3.connect(catalog)) as db, db:
                db.execute(
                    "INSERT INTO attempts(source_date,status,detail,created_at) VALUES (?,?,?,?)",
                    (day, status, detail, datetime.now(timezone.utc).isoformat()),
                )
            report["weeks"].append({"date": day, "status": status, "error": detail})
    report_path = root / "last_run.json"
    temporary = root / "last_run.tmp"
    temporary.write_text(json.dumps(report, indent=2), encoding="utf-8")
    os.replace(temporary, report_path)
    return report


def process_week(manager, catalog, root, work, python, cleaner, grid, recipe, day, shp):
    with tempfile.TemporaryDirectory(dir=work, prefix=day) as directory:
        stage = Path(directory)
        raw = stage / (shp.stem + "_M.zip")
        members = package_raw(shp, raw)
        size, sha = raw.stat().st_size, file_hash(raw)
        if size > settings.MAX_FILE_SIZE_BYTES:
            raise ValueError("USDM package exceeds configured ingestion limit")
        record, _ = manager.register_upload(
            raw, "usdm", day, DATASET_KEY, raw.name, "usdm-replay", sha, size
        )
        identity = {"file_id": record.file_id, "raw_sha256": sha, "recipe": recipe}
        build = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        with closing(sqlite3.connect(catalog)) as db, db:
            existing = db.execute(
                "SELECT manifest FROM builds WHERE build_id=?", (build,)
            ).fetchone()
        if existing:
            verify_products(root, json.loads(existing[0]))
            return "skipped"
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
        for layer, name in [
            ("silver", "silver.parquet"),
            ("gold", "gold.csv"),
            ("quality", "quality.json"),
            ("reference", "grid.csv"),
        ]:
            path = grid if layer == "reference" else stage / name
            digest = file_hash(path)
            relative = (
                Path(layer)
                / "source=usdm"
                / f"week_date={day}"
                / f"build={build}"
                / f"{digest}{path.suffix}"
            )
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                if file_hash(destination) != digest:
                    raise ValueError("Existing product checksum mismatch")
            else:
                temp = destination.with_suffix(".tmp")
                with path.open("rb") as inp, temp.open("wb") as out:
                    shutil.copyfileobj(inp, out)
                    out.flush()
                    os.fsync(out.fileno())
                os.replace(temp, destination)
            manifest["products"][layer] = {"path": relative.as_posix(), "sha256": digest}
        verify_products(root, manifest)
        # All artifacts exist before the single atomic warehouse commit. An interrupted
        # build leaves unreferenced files which a retry can verify and adopt.
        with closing(sqlite3.connect(catalog)) as db, db:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA synchronous=FULL")
            db.execute(
                "INSERT INTO builds VALUES (?,?,?,?,?,?,?)",
                (
                    build,
                    record.file_id,
                    day,
                    record.revision,
                    sha,
                    json.dumps(manifest, sort_keys=True),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            with (stage / "gold.csv").open(encoding="utf-8", newline="") as stream:
                db.executemany(
                    "INSERT INTO gold_cells VALUES (?,?,?,?,?,?)",
                    (
                        (
                            build,
                            row["time"],
                            row["grid"],
                            float(row["lon"]),
                            float(row["lat"]),
                            row["drought"],
                        )
                        for row in csv.DictReader(stream)
                    ),
                )
        return "succeeded"
