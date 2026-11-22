"""Isolated GIS worker; reuses the supplied USDM cleaner without changing its source."""

import argparse
import importlib.util
import json
import sys
from dataclasses import asdict
from pathlib import Path


def load_cleaner(path):
    spec = importlib.util.spec_from_file_location("usdm_source_cleaner", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def prepare_grid(source, target):
    import importlib.metadata

    import pandas as pd

    grid = pd.read_csv(source, usecols=["grid", "lon", "lat"], dtype={"grid": str})
    grid = grid.drop_duplicates().sort_values("grid").reset_index(drop=True)
    if (
        grid.empty
        or grid.isna().any().any()
        or grid.grid.duplicated().any()
        or grid[["lon", "lat"]].duplicated().any()
        or not grid.lon.between(-180, 180).all()
        or not grid.lat.between(-90, 90).all()
    ):
        raise ValueError("Invalid or inconsistent grid coordinates")
    grid.to_csv(target, index=False, lineterminator="\n")
    target.with_suffix(".versions.json").write_text(
        json.dumps(
            {
                name: importlib.metadata.version(name)
                for name in ["geopandas", "shapely", "pandas", "pyarrow", "pyogrio", "numpy"]
            }
        ),
        encoding="utf-8",
    )


def process(cleaner_path, raw, day, grid_path, output):
    import geopandas as gpd
    import pandas as pd

    cleaner = load_cleaner(cleaner_path)
    pipeline = cleaner.USDMBronzeToSilverPipeline(
        cleaner.PipelineConfig(raw.parent, output, overwrite=True)
    )
    # Reject ambiguous science before the reused cleaner can coerce fractional DM
    # or silently assign a missing CRS.
    source = pipeline.read_bronze_feature_data(raw)
    if source.empty or source.crs is None or "DM" not in source:
        raise ValueError("Source requires nonempty polygons, DM and an explicit CRS")
    dm = pd.to_numeric(source.DM, errors="coerce")
    if dm.isna().any() or not dm.isin(range(5)).all():
        raise ValueError("DM must be an integer from 0 through 4")
    silver, metric = pipeline.process_week(day, day.replace("-", ""), raw)
    if (
        silver is None
        or metric.status != "SUCCESS"
        or metric.quarantined_features_count
        or not silver.geometry.is_valid.all()
        or not silver.geom_type.isin(["Polygon", "MultiPolygon"]).all()
    ):
        raise ValueError("Silver quality gate failed; no partial week may be published")
    bounds = silver.total_bounds
    if bounds[0] < -180 or bounds[2] > 180 or bounds[1] < -90 or bounds[3] > 90:
        raise ValueError("Geometry outside WGS84 bounds")
    # Remove wall-clock fields so retry produces the same logical dataset.
    silver = silver.drop(columns=["processed_at"])
    silver.to_parquet(output / "silver.parquet", compression="snappy")
    grid = pd.read_csv(grid_path, dtype={"grid": str})
    points = gpd.GeoDataFrame(
        grid, geometry=gpd.points_from_xy(grid.lon, grid.lat), crs="EPSG:4326"
    )
    joined = gpd.sjoin(points, silver[["dm_value", "geometry"]], how="left", predicate="within")
    # Explicit maximum severity for overlaps; outside all polygons is no drought.
    severity = joined.groupby("grid").dm_value.max()
    gold = grid.copy()
    gold.insert(0, "time", day.replace("-", ""))
    gold["drought"] = gold.grid.map(severity).map(
        lambda value: "0" if pd.isna(value) else f"D{int(value)}"
    )
    if len(gold) != len(grid) or gold.isna().any().any():
        raise ValueError("Incomplete Gold grid")
    gold.to_csv(output / "gold.csv", index=False, lineterminator="\n")
    counts = gold.groupby("drought").size()
    summary = {
        category: int(counts.get(category, 0)) for category in ["0", "D0", "D1", "D2", "D3", "D4"]
    }
    (output / "quality.json").write_text(
        json.dumps(
            {"silver": asdict(metric), "gold_cells": len(gold), "counts": summary}, indent=2
        ),
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--grid-source", type=Path)
    parser.add_argument("--grid", required=True, type=Path)
    parser.add_argument("--cleaner", type=Path)
    parser.add_argument("--raw", type=Path)
    parser.add_argument("--day")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.grid_source:
        prepare_grid(args.grid_source, args.grid)
    else:
        process(args.cleaner, args.raw, args.day, args.grid, args.output)


if __name__ == "__main__":
    main()
