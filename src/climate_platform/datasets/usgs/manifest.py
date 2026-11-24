"""USGS medallion run manifest and verification.

One job: create a versioned run directory, record its inputs/code/versions, enumerate the
outputs with checksums, and verify the whole dependency graph (including raw sources).
Scientific transforms live in ``silver``/``weekly``/``gold``.
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from importlib.metadata import version
from pathlib import Path

import pyarrow.parquet as pq

from climate_platform.common.clock import utc_now_iso
from climate_platform.datasets.usgs.method import METHOD
from climate_platform.medallion.io import file_hash, write_json_atomic


def inputs(paths):
    return [{"path": str(Path(p).resolve()), "sha256": file_hash(p)} for p in paths]


def save(df, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def read(path):
    return pq.ParquetFile(path).read().to_pandas()


def verified(run, expected_stage=None, _active=None, _checked=None):
    """Verify the entire manifest dependency graph, including raw sources."""
    run = Path(run).resolve()
    active = set() if _active is None else _active
    checked = {} if _checked is None else _checked
    if run in active:
        raise ValueError(f"Cyclic manifest dependency: {run}")
    m = json.loads((run / "manifest.json").read_text())
    if expected_stage is not None and m.get("stage") != expected_stage:
        raise ValueError(f"Expected {expected_stage} stage: {run}")
    if run in checked:
        return checked[run]
    if m["status"] != "complete" or m["method"] != METHOD:
        raise ValueError("Upstream run incomplete or method incompatible")
    active.add(run)
    for item in m["sources"]:
        if file_hash(item["path"]) != item["sha256"]:
            raise ValueError(f"Source checksum mismatch: {item['path']}")
        source = Path(item["path"])
        if source.name == "manifest.json":
            parent = json.loads(source.read_text())
            if "method" in parent and "stage" in parent:
                verified(source.parent, _active=active, _checked=checked)
    for item in m["outputs"]:
        if file_hash(run / item["path"]) != item["sha256"]:
            raise ValueError(f"Upstream checksum mismatch: {item['path']}")
    active.remove(run)
    checked[run] = m
    return m


@contextmanager
def stage(root, name, sources):
    run = root / "medallion" / name / str(time.time_ns())
    run.mkdir(parents=True)
    code = list(Path(__file__).parent.glob("*.py"))
    m = {
        "manifest_version": 2,
        # ``weekly`` is a declared intermediate tier built under the Silver root; record its
        # own stage name instead of reporting it as a Silver layer.
        "layer": name,
        "status": "running",
        "stage": name,
        "created_at": utc_now_iso(),
        "method": METHOD,
        "sources": inputs(sources),
        "code": inputs(code),
        "outputs": [],
    }
    m["versions"] = {
        name: version(name)
        for name in ["pandas", "numpy", "pyarrow", "geopandas", "shapely", "pyogrio"]
    }
    write_json_atomic(run / "manifest.json", m)
    try:
        yield run, m
        m["outputs"] = [
            {"path": str(p.relative_to(run)), "sha256": file_hash(p)}
            for p in sorted(run.rglob("*"))
            if p.is_file() and p.name != "manifest.json"
        ]
        for item in m["outputs"]:
            if item["path"].endswith(".parquet"):
                parquet = pq.ParquetFile(run / item["path"])
                item["rows"] = parquet.metadata.num_rows
                item["schema"] = [
                    {"name": f.name, "type": str(f.type), "nullable": f.nullable}
                    for f in parquet.schema_arrow
                ]
        m.update(status="complete", completed_at=utc_now_iso())
    except BaseException as exc:
        m.update(status="incomplete", error=str(exc))
        raise
    finally:
        write_json_atomic(run / "manifest.json", m)
