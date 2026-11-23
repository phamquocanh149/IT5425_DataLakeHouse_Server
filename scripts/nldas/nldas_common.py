"""Shared NLDAS medallion helpers for Server-side scripts.

Readiness, inventory and publication mechanics shared by ``silver_common`` and
``gold_common``. The scientific transformations stay in the layer modules so
Silver and Gold do not share a science module, mirroring the validated
``duy-nldas-script`` split.

Workspace defaults: Bronze and references are read from
``../duy-nldas-script/src``; Silver and Gold are written under
``data_lake/{silver,gold}/nldas``. Every CLI accepts explicit paths, and the
defaults can be changed with ``NLDAS_BRONZE_ROOT``, ``NLDAS_REFERENCES_DIR``,
``NLDAS_SILVER_ROOT``, ``NLDAS_GOLD_ROOT`` and ``NLDAS_LOCK_FILE``.
"""

import csv
import hashlib
import json
import os
import re
import sys
from contextlib import contextmanager
from datetime import datetime, time, timedelta
from pathlib import Path

HERE = Path(__file__).resolve()
SERVER_ROOT = HERE.parents[2]
WORKSPACE = HERE.parents[3]
DUY_ROOT = WORKSPACE / "duy-nldas-script"

PRODUCTS = ("FORA", "NOAH")
PROFILE = "matlab_original"

VARIABLES = {
    "FORA": {"apcp": ("Rainf", "kg m-2"), "pevap": ("PotEvap", "kg m-2")},
    "NOAH": {
        "evp": ("Evap", "kg m-2"),
        "pevpr": ("PotEvap", "W m-2"),
        "soilm": ("SoilM_0_10cm", "kg m-2"),
        "ssrun": ("Qs", "kg m-2"),
        "tsoil": ("SoilT_0_10cm", "K"),
        "lai": ("LAI", "unitless"),
        "snod": ("SnowDepth", "m"),
        "snom": ("Qsm", "kg m-2"),
        "snowc": ("SnowFrac", "fraction"),
        "weasd": ("SWE", "kg m-2"),
    },
}


def _env_path(name, default):
    value = os.environ.get(name)
    return Path(value) if value else default


def default_bronze_root():
    return _env_path("NLDAS_BRONZE_ROOT", DUY_ROOT / "src" / "bronze" / "data")


def default_references():
    return _env_path("NLDAS_REFERENCES_DIR", DUY_ROOT / "src" / "references")


def default_silver_root():
    return _env_path("NLDAS_SILVER_ROOT", SERVER_ROOT / "data_lake" / "silver" / "nldas")


def default_gold_root():
    return _env_path("NLDAS_GOLD_ROOT", SERVER_ROOT / "data_lake" / "gold" / "nldas")


def default_lock_file():
    return _env_path("NLDAS_LOCK_FILE", SERVER_ROOT / "data_lake" / "temp" / "nldas_medallion.lock")


def resolve_products(value):
    if value.lower() == "both":
        return list(PRODUCTS)
    product = value.upper()
    if product not in PRODUCTS:
        raise ValueError(f"Unknown product: {value}")
    return [product]


def configure_stdio():
    """Keep Vietnamese workspace paths printable when stdout is a legacy console."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def file_pattern(product):
    """Match the NLDAS hourly filename used by the crawl engine."""
    return re.compile(r"nldas_" + product.lower() + r"0125_h\.a(\d{8})\.(\d{4})", re.I)


def inventory(directory, product):
    """Return ``{datetime: Path}`` for every NLDAS hour under ``directory``."""
    pattern = file_pattern(product)
    records = {}
    for path in sorted(Path(directory).rglob("*.nc")):
        match = pattern.search(path.name)
        if not match:
            continue
        stamp = datetime.strptime("".join(match.groups()), "%Y%m%d%H%M")
        if stamp in records:
            raise ValueError(f"Duplicate {product} timestamp {stamp}: {records[stamp]} and {path}")
        records[stamp] = path
    return records


def week_hours(week_date):
    """The 168 source hours ending at ``week_date`` (Tuesday) 00:00."""
    end = datetime.combine(week_date, time.min)
    return [end - timedelta(hours=168 - index) for index in range(168)]


def missing_hours(week_date, records):
    return [hour for hour in week_hours(week_date) if hour not in records]


def ready_weeks(dates, inventories):
    """Per product, reference weeks whose 168 hours are all present in Bronze."""
    ready = {product: [] for product in inventories}
    for week_date in dates:
        hours = week_hours(week_date)
        for product, records in inventories.items():
            if all(hour in records for hour in hours):
                ready[product].append(week_date)
    return ready


def load_week_dates(path):
    """Read the reference Tuesday calendar without requiring pandas."""
    with Path(path).open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows or "week_date" not in rows[0]:
        raise ValueError(f"Expected a week_date column in {path}")
    dates = [datetime.strptime(row["week_date"], "%Y-%m-%d").date() for row in rows]
    if len(set(dates)) != len(dates):
        raise ValueError("Reference week dates are duplicated")
    if dates != sorted(dates):
        raise ValueError("Reference week dates must increase")
    if any(day.weekday() != 1 for day in dates):
        raise ValueError("Reference week dates must be Tuesdays")
    return dates


def write_json_atomic(path, payload):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temporary, target)


@contextmanager
def exclusive_run(path):
    """Non-blocking OS lock so scheduled runs cannot merge partitions concurrently."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a+b") as stream:
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            if not stream.read(1):
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError(f"NLDAS medallion already running (lock: {target})") from exc
        else:
            import fcntl

            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise RuntimeError(f"NLDAS medallion already running (lock: {target})") from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def require(modules, purpose):
    missing = []
    for name in modules:
        try:
            __import__(name)
        except ModuleNotFoundError:
            missing.append(name)
    if missing:
        raise RuntimeError(
            f"{purpose} requires {', '.join(modules)} in the running interpreter; "
            f"missing: {', '.join(missing)}"
        )


def reference_grid_size(references_dir):
    require(["pandas"], "Reading the reference grid")
    import pandas as pd

    return len(pd.read_parquet(Path(references_dir) / "grid_reference.parquet"))


def silver_complete_weeks(silver_root, product, *, grid_size):
    """Weeks already present in Silver with a full grid and 168 valid hours."""
    require(["pandas", "pyarrow"], "Inspecting Silver")
    import pandas as pd

    complete = set()
    directory = Path(silver_root) / product
    columns = ["week_date", "quality_status"]
    columns += [f"{name}_valid_hours" for name in VARIABLES[product]]
    for path in sorted(directory.glob("year=*/data.parquet")):
        frame = pd.read_parquet(path, columns=columns)
        for week, chunk in frame.groupby("week_date"):
            if len(chunk) != grid_size:
                continue
            if not (chunk["quality_status"] == "complete").all():
                continue
            if all((chunk[f"{name}_valid_hours"] == 168).all() for name in VARIABLES[product]):
                complete.add(pd.Timestamp(week).date())
    return complete


def gold_complete_weeks(gold_root, product, *, grid_size):
    """Weeks already published to Gold with complete quality status."""
    require(["pandas", "pyarrow"], "Inspecting Gold")
    import pandas as pd

    complete = set()
    directory = Path(gold_root) / product
    for path in sorted(directory.glob("year=*/data.parquet")):
        frame = pd.read_parquet(path, columns=["week_date", "quality_status"])
        for week, chunk in frame.groupby("week_date"):
            if len(chunk) not in (grid_size, grid_size - 1):
                continue
            if (chunk["quality_status"] == "complete").all():
                complete.add(pd.Timestamp(week).date())
    return complete


def load_references_grid(grid_path):
    import numpy as np
    import pandas as pd

    coords = pd.read_parquet(grid_path)
    if list(coords.columns) != ["grid_id", "lon", "lat"]:
        raise ValueError("Expected grid_id, lon, lat columns in reference grid")
    if coords.empty or coords.isna().any().any() or coords.grid_id.duplicated().any():
        raise ValueError("Empty, missing or duplicate reference grid")
    if not np.isfinite(coords[["lon", "lat"]].to_numpy(dtype=float)).all():
        raise ValueError("Non-finite reference coordinates")
    if coords.duplicated(["lon", "lat"]).any():
        raise ValueError("Duplicate reference coordinates")
    return coords.reset_index(drop=True)


def write_partition(frame, directory, metadata, incompatible):
    import pandas as pd

    directory.mkdir(parents=True, exist_ok=True)
    existing = directory / "schema_metadata.json"
    if existing.exists():
        old = json.loads(existing.read_text(encoding="utf-8"))
        for key in incompatible:
            if old.get(key) != metadata[key]:
                raise ValueError(f"Incompatible {key}; choose a new output directory")
    # Merge with existing dates so processing another month cannot erase prior weeks.
    for year, chunk in frame.groupby(frame.week_date.dt.year):
        target = directory / f"year={year}" / "data.parquet"
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            old = pd.read_parquet(target)
            if set(old.columns) != set(chunk.columns):
                raise ValueError(f"Incompatible existing schema: {target}")
            old = old[~old.week_date.isin(chunk.week_date.unique())]
            chunk = pd.concat([old, chunk], ignore_index=True)
        if chunk.duplicated(["grid_id", "week_date"]).any():
            raise ValueError("Duplicate output keys")
        target_tmp = target.with_suffix(".tmp.parquet")
        chunk.sort_values(["week_date", "grid_id"]).to_parquet(target_tmp, index=False)
        target_tmp.replace(target)
    (directory / "schema_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
