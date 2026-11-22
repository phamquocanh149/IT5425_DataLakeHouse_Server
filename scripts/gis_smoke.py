"""Real GIS -> Bronze/Silver/Gold -> checkpoint -> independent restore and rerun.

Uses synthetic polygons in a fresh temporary root, never workstation source data.
Run inside the release worker image, or supply a separate --gis-python locally.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gis-python", default=sys.executable)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="medallion-drill-") as directory:
        root = Path(directory)
        source, runtime = root / "source", root / "runtime"
        source.mkdir()
        os.environ.update(
            BASE_DIR=str(runtime),
            STORAGE_BACKEND="local",
            DEBUG="False",
            API_KEYS="[]",
            ENABLE_STATIC_KEYS="True",
            COLLECTOR_API_KEY="drill-only-collector",
            ADMIN_API_KEY="drill-only-admin",
            ENABLE_LEGACY_KEYS="False",
            DATA_LAKE_DIR="data_lake",
            METADATA_DIR="metadata",
            TEMP_DIR="data_lake/temp",
        )
        from climate_platform.config import settings
        from climate_platform.datasets.usdm.processor import run_pipeline
        from scripts.medallion_backup import create, restore, reconcile, verify

        code = """
from pathlib import Path
import sys
import geopandas as gpd
from shapely.geometry import box
root = Path(sys.argv[1])
folder = root / "bronze/data/shp/USDM_20200107_M"
folder.mkdir(parents=True)
gpd.GeoDataFrame({"DM":[1,4]}, geometry=[box(-102,33,-98,37),box(-101,34,-99,36)],
                crs="EPSG:4326").to_file(folder / "USDM_20200107.shp")
grid = root / "gold/data/usdmfinal.csv"
grid.parent.mkdir(parents=True)
grid.write_text("grid,lon,lat\\nA,-100,35\\nB,-120,40\\n", encoding="utf-8")
"""
        subprocess.run([args.gis_python, "-c", code, str(source)], check=True, timeout=60)
        first = run_pipeline(source, runtime / "products", args.gis_python)
        assert first["succeeded"] == 1 and first["failed"] == 0, first
        bundle = root / "checkpoint"
        manifest = create(runtime, bundle, images=["synthetic-local-drill"], writers_stopped=True)
        verify(bundle)
        restored = root / "restored"
        result = restore(bundle, restored)
        assert result["observations"] == result["builds"] == 1
        assert result["gold_rows"] == 2
        settings.BASE_DIR = restored
        replay = run_pipeline(source, restored / "products", args.gis_python)
        assert replay["skipped"] == 1 and replay["failed"] == 0, replay
        assert reconcile(restored) == result
        print(
            json.dumps(
                {
                    "status": "passed",
                    "scope": "real GIS, synthetic local data",
                    "checkpoint": manifest["checkpoint_utc"],
                    "restored": result,
                    "replay": replay,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
