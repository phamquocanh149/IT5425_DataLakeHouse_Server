"""NLDAS reference grid loading.

One job: load and validate the reference grid (``grid_id``, ``lon``, ``lat``) used to align
NLDAS blocks, plus its row count.
"""

from __future__ import annotations

from pathlib import Path

from climate_platform.datasets.nldas.deps import require


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


def reference_grid_size(references_dir):
    require(["pandas"], "Reading the reference grid")
    import pandas as pd

    return len(pd.read_parquet(Path(references_dir) / "grid_reference.parquet"))
