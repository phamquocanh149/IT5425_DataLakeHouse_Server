#!/usr/bin/env python3
"""Map EXISTING USDM grid centres to WBD HUC8 polygons. See README.md.
No nearest-neighbour assignment, grid regeneration, or silent boundary choice.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd


def read_grid(path, id_col, lon_col, lat_col):
    df = pd.read_csv(path, dtype={id_col: "string"})
    required = [id_col, lon_col, lat_col]
    if not set(required).issubset(df.columns):
        raise ValueError(f"Grid CSV needs columns: {required}")
    df = df[required].rename(columns={id_col: "grid_id", lon_col: "Lon", lat_col: "Lat"})
    if df.isna().any().any() or df.grid_id.str.strip().eq("").any():
        raise ValueError("Missing grid ID or coordinates")
    for c in ["Lon", "Lat"]:
        df[c] = pd.to_numeric(df[c], errors="raise")
    if not (df.Lon.between(-180, 180) & df.Lat.between(-90, 90)).all():
        raise ValueError("Grid CSV must contain WGS84 longitude/latitude in degrees")
    # Weekly USDM tables may repeat the same grid; accept only identical centres.
    df = df.drop_duplicates()
    if df.grid_id.duplicated().any():
        raise ValueError("One grid_id has multiple coordinates")
    if df.duplicated(["Lon", "Lat"]).any():
        raise ValueError("Multiple grid IDs share the same centre")
    return df.reset_index(drop=True)


def read_huc(path, layer, huc_field):
    w = gpd.read_file(path, **({"layer": layer} if layer else {}))
    matches = [c for c in w.columns if c.lower() == huc_field.lower()]
    if len(matches) != 1:
        raise ValueError(f"Cannot find unique {huc_field}; columns: {list(w.columns)}")
    if w.crs is None:
        raise ValueError("WBD has no CRS. Obtain source CRS; do not guess EPSG:4326")
    original_crs = str(w.crs)
    s = w[matches[0]]
    # Reject numeric HUC fields: leading zeroes may already have been lost.
    if not s.map(lambda v: isinstance(v, str)).all():
        raise ValueError(
            "HUC8 must be an 8-character STRING; do not silently zero-pad numeric data"
        )
    w = w[[matches[0], w.geometry.name]].rename(columns={matches[0]: "huc8"})
    w["huc8"] = w.huc8.str.strip()
    if not w.huc8.str.fullmatch(r"\d{8}").all():
        raise ValueError("Invalid HUC8 code: require exactly 8 digits")
    if w.geometry.isna().any() or w.geometry.is_empty.any():
        raise ValueError("Empty WBD geometry")
    if not w.geom_type.isin(["Polygon", "MultiPolygon"]).all() or not w.is_valid.all():
        raise ValueError("Invalid/non-polygon WBD geometry. Repair explicitly and document changes")
    # Dissolve multipart/duplicate records of the SAME HUC only.
    w = w.dissolve(by="huc8", as_index=False).reset_index(drop=True)
    return w, original_crs


def map_grid(grid, w):
    points = gpd.GeoDataFrame(
        grid.copy(), geometry=gpd.points_from_xy(grid.Lon, grid.Lat), crs="EPSG:4326"
    ).to_crs(w.crs)
    inside = gpd.sjoin(points, w[["huc8", "geometry"]], how="left", predicate="within")
    touching = gpd.sjoin(points, w[["huc8", "geometry"]], how="left", predicate="intersects")

    def grouped(frame):
        return frame.groupby(level=0)["huc8"].agg(lambda s: sorted(set(s.dropna())))

    ins, hits = grouped(inside), grouped(touching)
    out = grid.copy()
    codes, statuses, candidates = [], [], []
    for i in grid.index:
        a, b = ins.get(i, []), hits.get(i, [])
        if len(a) == 1 and len(b) == 1:
            code, status = a[0], "inside"
        elif len(a) > 1 or (len(a) == 1 and len(b) > 1):
            code, status = None, "overlap_ambiguous"
        elif len(b) == 1:
            code, status = b[0], "boundary_unique"
        elif len(b) > 1:
            code, status = None, "boundary_ambiguous"
        else:
            code, status = None, "unmatched"
        codes.append(code)
        statuses.append(status)
        candidates.append("|".join(b))
    out["huc8"] = pd.Series(codes, dtype="string")
    out["huc6"] = out.huc8.str[:6]
    out["huc4"] = out.huc8.str[:4]
    out["match_status"] = statuses
    out["candidate_huc8"] = candidates
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--grid", required=True, help="Existing USDM grid/weekly CSV, WGS84 centres")
    p.add_argument("--wbd", required=True, help="Extracted .gdb directory, .gpkg or .shp")
    p.add_argument("--layer", help="For GDB typically WBDHU8; omit for shapefile")
    p.add_argument("--huc-field", default="huc8")
    p.add_argument("--id-col", default="grid_id")
    p.add_argument("--lon-col", default="lon")
    p.add_argument("--lat-col", default="lat")
    p.add_argument("--out", default="grid_huc_output")
    p.add_argument(
        "--allow-unresolved",
        action="store_true",
        help="Return exit 0 despite unresolved rows; still leave codes null",
    )
    a = p.parse_args()
    outdir = Path(a.out)
    if outdir.exists() and any(outdir.iterdir()):
        raise ValueError("Output directory is nonempty; choose a new directory")
    grid = read_grid(a.grid, a.id_col, a.lon_col, a.lat_col)
    w, source_crs = read_huc(a.wbd, a.layer, a.huc_field)
    result = map_grid(grid, w)
    outdir.mkdir(parents=True, exist_ok=True)
    result.to_csv(outdir / "grid_huc.csv", index=False)
    result.to_parquet(outdir / "grid_huc.parquet", index=False)
    unresolved = result.huc8.isna()
    result[unresolved].to_csv(outdir / "review_unresolved.csv", index=False)
    report = {
        "grid_rows": len(result),
        "unique_huc8_polygons": len(w),
        "status_counts": result.match_status.value_counts().to_dict(),
        "unresolved_rows": int(unresolved.sum()),
        "source_wbd": str(Path(a.wbd).resolve()),
        "source_layer": a.layer,
        "source_crs": source_crs,
        "source_grid": str(Path(a.grid).resolve()),
        "grid_sha256": hashlib.sha256(Path(a.grid).read_bytes()).hexdigest(),
        "grid_input_crs": "EPSG:4326",
        "method": "centre within; exact boundary intersects; ambiguous/unmatched left null",
        "geopandas_version": gpd.__version__,
        "note": "HUC6/HUC4 are prefixes of HUC8 from the same WBD vintage. No nearest fill.",
    }
    (outdir / "qa_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 2 if unresolved.any() and not a.allow_unresolved else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
