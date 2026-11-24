"""NLDAS Silver -> Gold science.

One job: assemble the ML-ready Gold table from Silver, verify the grid/coordinates, reject
partial-week values and drop cell ``R25`` unless requested. No orchestration, no lock.
"""

from __future__ import annotations

import json
from pathlib import Path

from climate_platform.datasets.nldas import references, spec
from climate_platform.datasets.nldas.deps import require
from climate_platform.datasets.nldas.partition import write_partition
from climate_platform.medallion.io import file_hash

GOLD_INCOMPATIBLE = ("profile", "version", "grid_reference_sha256", "r25_policy")


def build_metadata(product, grid_path, keep_r25):
    return {
        "product": product,
        "profile": spec.PROFILE,
        "version": "1.0",
        "grid_reference_sha256": file_hash(grid_path),
        "units": {name: unit for name, (_, unit) in spec.VARIABLES[product].items()},
        "r25_policy": "keep" if keep_r25 else "drop",
    }


def build_gold(
    product,
    *,
    silver_input,
    references_dir,
    gold_output,
    start=None,
    end=None,
    weeks=None,
    keep_r25=False,
    log=print,
):
    """Build Gold Parquet for ``product`` from Silver partitions."""
    if product not in spec.VARIABLES:
        raise ValueError(f"Unknown product: {product}")
    require(["numpy", "pandas", "pyarrow"], "NLDAS Gold")
    import numpy as np
    import pandas as pd

    references_dir = Path(references_dir)
    grid_path = references_dir / "grid_reference.parquet"
    grid = references.load_references_grid(grid_path)
    metadata = build_metadata(product, grid_path, keep_r25)

    paths = sorted(Path(silver_input).glob("year=*/data.parquet"))
    if not paths:
        raise ValueError(f"Run Silver first; no partitions under {silver_input}")
    frame = pd.concat([pd.read_parquet(path) for path in paths], ignore_index=True)
    if start:
        frame = frame[frame.week_date >= pd.Timestamp(start)]
    if end:
        frame = frame[frame.week_date <= pd.Timestamp(end)]
    if weeks is not None:
        requested = pd.DatetimeIndex(sorted({pd.Timestamp(day) for day in weeks}))
        frame = frame[frame.week_date.isin(requested)]
    if frame.empty:
        raise ValueError("No Silver rows in selected dates")
    if set(frame.aggregation_profile.unique()) != {spec.PROFILE}:
        raise ValueError("Unexpected Silver aggregation profile")
    if frame.duplicated(["grid_id", "week_date"]).any():
        raise ValueError("Duplicate Silver keys")
    check = frame.merge(
        grid, on="grid_id", suffixes=("", "_expected"), how="left", validate="many_to_one"
    )
    if not (
        np.allclose(check.lat, check.lat_expected) and np.allclose(check.lon, check.lon_expected)
    ):
        raise ValueError("Silver coordinates do not match reference grid")
    if not (frame.groupby("week_date").size() == len(grid)).all():
        raise ValueError("Silver grid is incomplete")
    for name in spec.VARIABLES[product]:
        if frame.loc[frame[f"{name}_valid_hours"] != 168, name].notna().any():
            raise ValueError("Silver contains partial-week values")
    if not keep_r25:
        frame = frame[frame.grid_id != "R25"]
    columns = ["grid_id", "week_date", "lat", "lon"]
    columns += list(spec.VARIABLES[product])
    columns += [
        "quality_status",
        "n_source_hours",
        "source_manifest_id",
        "processing_version",
        "aggregation_profile",
    ]
    frame = frame[columns]
    output = Path(gold_output)
    existing_meta = output / "schema_metadata.json"
    if existing_meta.exists():
        old = json.loads(existing_meta.read_text(encoding="utf-8"))
        if old["r25_policy"] != metadata["r25_policy"]:
            raise ValueError("Use a different output directory when changing R25 policy")
    write_partition(frame, output, metadata, GOLD_INCOMPATIBLE)
    log(f"Wrote {len(frame)} rows to {output}")
    return {
        "product": product,
        "weeks": sorted({pd.Timestamp(day).date().isoformat() for day in frame.week_date}),
        "rows": len(frame),
        "output": str(output),
    }
