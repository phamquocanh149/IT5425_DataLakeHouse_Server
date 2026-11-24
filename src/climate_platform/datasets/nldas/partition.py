"""NLDAS partition writing.

One job: merge a frame into ``year=YYYY/data.parquet`` partitions atomically, preserving
other weeks and refusing an incompatible schema/profile directory.
"""

from __future__ import annotations

from climate_platform.medallion.io import atomic_write, read_json, write_json_atomic


def write_partition(frame, directory, metadata, incompatible):
    import pandas as pd

    directory.mkdir(parents=True, exist_ok=True)
    existing = directory / "schema_metadata.json"
    if existing.exists():
        old = read_json(existing)
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
        # Atomic write: an interrupted run never leaves a truncated final partition.
        with atomic_write(target) as temporary:
            chunk.sort_values(["week_date", "grid_id"]).to_parquet(temporary, index=False)
    write_json_atomic(directory / "schema_metadata.json", metadata)
