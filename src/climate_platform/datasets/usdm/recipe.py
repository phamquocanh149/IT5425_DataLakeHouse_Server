"""USDM build recipe preparation.

One job: snapshot the cleaner/worker/grid bytes and archive the exact executable recipe for a
build, so a historical build can be reproduced and verified. No per-week processing here.
"""

from __future__ import annotations

import json
import os
import shutil

from climate_platform.config import settings
from climate_platform.datasets.usdm.worker import WORKER
from climate_platform.medallion.io import file_hash


def prepare_recipe(source, root, work, python, run_worker):
    """Copy cleaner/grid into ``work``, prepare the grid, and archive the recipe bytes."""
    cleaner = work / "cleaner.py"
    cleaner_source = source / "silver/scripts/usdm_bronze_to_silver.py"
    if not cleaner_source.exists():
        # Read-only package resource (byte-pinned vendored cleaner) for installed runs.
        cleaner_source = settings.package_resources / "usdm_bronze_to_silver.py"
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
    return cleaner, grid, recipe
