"""Real GIS worker tests: auto-discovered interpreter, ``USDM_GIS_PYTHON`` to override.

A GIS interpreter is searched for by default (env override, then a conventional ``.venv-gis``)
so the end-to-end drought-classification suite actually runs wherever the GIS stack exists
instead of silently skipping. The classification contract itself is also guarded by
``test_drought_classification`` which runs without any GIS stack. Set ``REQUIRE_GIS_TESTS=1``
to turn a missing GIS environment into a hard failure (the release gate relies on this).
"""

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def gis_python():
    """Return a GIS interpreter if one is configured or discoverable, else ``None``."""
    override = os.environ.get("USDM_GIS_PYTHON")
    if override:
        return override
    for venv in (REPO_ROOT / ".venv-gis", REPO_ROOT / "venv-gis", REPO_ROOT / ".gis"):
        for relative in ("bin/python", "bin/python3", "Scripts/python.exe"):
            candidate = venv / relative
            if candidate.exists():
                return str(candidate)
    return None


@pytest.mark.gis
@pytest.mark.parametrize("case", ["overlap", "repair", "fractional", "out_of_range", "missing_crs"])
def test_real_gis_quality_gates(tmp_path, case):
    python = gis_python()
    source = os.environ.get("USDM_SOURCE_ROOT")
    cleaner = (
        Path(source) / "silver/scripts/usdm_bronze_to_silver.py"
        if source
        else REPO_ROOT / "src/climate_platform/datasets/usdm/resources/usdm_bronze_to_silver.py"
    )
    if not python:
        if os.environ.get("REQUIRE_GIS_TESTS") == "1":
            pytest.fail("Required GIS environment missing: set USDM_GIS_PYTHON or create .venv-gis")
        pytest.skip("No GIS interpreter: set USDM_GIS_PYTHON or create .venv-gis")
    assert cleaner.is_file(), "Required cleaner missing"
    code = r"""
import sys
from pathlib import Path
import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon, box
from climate_platform.datasets.usdm.science import process
root, source, case = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
raw = root / "USDM_20200107.shp"
dm = [1, 4]
geometries = [box(-102, 33, -98, 37), box(-101, 34, -99, 36)]
if case == "fractional": dm[0] = 0.5
if case == "out_of_range": dm[0] = 5
if case == "repair":
    geometries[0] = Polygon([(-102,33),(-98,37),(-102,37),(-98,33),(-102,33)])
gpd.GeoDataFrame({"DM":dm}, geometry=geometries,
    crs=None if case == "missing_crs" else "EPSG:4326").to_file(raw)
grid = root / "grid.csv"
grid.write_text("grid,lon,lat\nA,-100,35\nB,-120,40\n", encoding="utf-8")
out = root / "out"
out.mkdir()
try:
    process(source, raw, "2020-01-07", grid, out)
except ValueError:
    assert case in {"fractional", "out_of_range", "missing_crs"}
    assert not (out / "gold.csv").exists()
else:
    assert case in {"overlap", "repair"}
    gold = pd.read_csv(out / "gold.csv").set_index("grid")
    assert gold.loc["A", "drought"] == "D4"
    assert gold.loc["B", "drought"] == "0"
    silver = gpd.read_parquet(out / "silver.parquet")
    assert silver.geometry.is_valid.all()
    assert "processed_at" not in silver.columns
"""
    result = subprocess.run(
        [python, "-c", code, str(tmp_path), str(cleaner), case],
        cwd=str(REPO_ROOT / "src"),
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")
