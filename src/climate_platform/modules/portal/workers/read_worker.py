"""Bounded, disposable reader for Portal JSON/SQLite; no GIS or network imports."""

import json
import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

MEMORY_BYTES = 256 * 1024 * 1024


def memory_limit():
    if os.name != "nt":
        import resource

        try:
            resource.setrlimit(resource.RLIMIT_AS, (MEMORY_BYTES, MEMORY_BYTES))
        except (ValueError, OSError):
            # macOS rejects RLIMIT_AS (and RLIMIT_DATA/RSS); the subprocess timeout and the
            # output-size caps still bound the reader, so this stays best-effort there.
            pass
        return None
    import ctypes as c
    from ctypes import wintypes as w

    class Basic(c.Structure):
        _fields_ = [
            ("ProcessTime", c.c_int64),
            ("JobTime", c.c_int64),
            ("Flags", w.DWORD),
            ("MinWorkingSet", c.c_size_t),
            ("MaxWorkingSet", c.c_size_t),
            ("ActiveProcessLimit", w.DWORD),
            ("Affinity", c.c_size_t),
            ("PriorityClass", w.DWORD),
            ("SchedulingClass", w.DWORD),
        ]

    class IO(c.Structure):
        _fields_ = [
            (name, c.c_uint64)
            for name in ("ReadOps", "WriteOps", "OtherOps", "ReadBytes", "WriteBytes", "OtherBytes")
        ]

    class Extended(c.Structure):
        _fields_ = [
            ("Basic", Basic),
            ("IO", IO),
            ("ProcessMemoryLimit", c.c_size_t),
            ("JobMemoryLimit", c.c_size_t),
            ("PeakProcessMemory", c.c_size_t),
            ("PeakJobMemory", c.c_size_t),
        ]

    kernel = c.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.restype = w.HANDLE
    kernel.CreateJobObjectW.argtypes = [c.c_void_p, w.LPCWSTR]
    kernel.SetInformationJobObject.argtypes = [w.HANDLE, c.c_int, c.c_void_p, w.DWORD]
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
    handle = kernel.CreateJobObjectW(None, None)
    info = Extended()
    info.Basic.Flags = 0x100  # JOB_OBJECT_LIMIT_PROCESS_MEMORY
    info.ProcessMemoryLimit = MEMORY_BYTES
    if (
        not handle
        or not kernel.SetInformationJobObject(handle, 9, c.byref(info), c.sizeof(info))
        or not kernel.AssignProcessToJobObject(handle, kernel.GetCurrentProcess())
    ):
        raise OSError("Cannot enforce reader memory limit")
    return handle  # Process exit closes the handle, keeping the limit for its entire lifetime.


def read_json(path, maximum):
    with Path(path).open("rb") as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise OverflowError()
    return json.loads(raw)


def run(job):
    if job["operation"] == "gold":
        with closing(sqlite3.connect(Path(job["path"]).as_uri() + "?mode=ro", uri=True)) as db:
            db.row_factory = sqlite3.Row
            rows = [
                dict(r)
                for r in db.execute(
                    "SELECT time,grid,lon,lat,drought FROM gold_cells WHERE build_id=? AND (? IS NULL OR drought=?) AND (? IS NULL OR grid=?) ORDER BY grid LIMIT 5001",
                    (
                        job["build"],
                        job.get("drought"),
                        job.get("drought"),
                        job.get("grid"),
                        job.get("grid"),
                    ),
                )
            ]
        if len(rows) > 5000:
            raise OverflowError()
        return rows
    if job["operation"] == "table":
        return read_json(job["path"], 1024 * 1024)
    west, south, east, north = job["bbox"]
    if job["layer"] == "silver":
        item = read_json(job["path"], 8 * 1024 * 1024)
        features = [
            f
            for f in item["features"]
            if f["bbox"][0] <= east
            and f["bbox"][2] >= west
            and f["bbox"][1] <= north
            and f["bbox"][3] >= south
            and (not job.get("drought") or f["properties"]["drought"] == job["drought"])
        ]
        metadata = item["metadata"]
    else:
        features = [
            {
                "type": "Feature",
                "id": r["grid"],
                "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
                "properties": r,
            }
            for r in job["rows"]
            if west <= r["lon"] <= east and south <= r["lat"] <= north
        ]
        metadata = {"geometry_simplified": False, "tolerance_degrees": 0}

    def vertices(coords):
        if coords and isinstance(coords[0], (int, float)):
            return 1
        return sum(vertices(c) for c in coords)

    if (
        len(features) > 5000
        or sum(vertices(f["geometry"]["coordinates"]) for f in features) > 100000
    ):
        raise OverflowError()
    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": metadata
        | {
            "feature_count": len(features),
            "selection_id": job["selection_id"],
            "release_id": job["release_id"],
        },
    }


if __name__ == "__main__":
    try:
        handle = memory_limit()
        job = json.loads(sys.stdin.buffer.read(1024 * 1024 + 1))
        output = json.dumps(run(job), ensure_ascii=True).encode()
        if len(output) > (5 * 1024 * 1024 if job["operation"] == "map" else 1024 * 1024):
            raise OverflowError()
        sys.stdout.buffer.write(output)
    except (MemoryError, OverflowError):
        sys.exit(3)
    except Exception:
        sys.exit(2)
