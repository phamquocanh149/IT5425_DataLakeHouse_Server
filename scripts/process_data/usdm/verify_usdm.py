"""Verify published products, source immutability and Gold concordance (read-only)."""

import argparse
import csv
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify(source, output, registry):
    with closing(
        sqlite3.connect(
            output.resolve().joinpath("warehouse.sqlite3").as_uri() + "?mode=ro", uri=True
        )
    ) as db:
        db.execute("ATTACH DATABASE ? AS registry", (registry.resolve().as_uri() + "?mode=ro",))
        builds = db.execute("""
            SELECT build_id,source_date,manifest FROM (
                SELECT b.*,row_number() OVER (
                    PARTITION BY b.file_id ORDER BY completed_at DESC,build_id DESC) AS rank
                FROM builds b JOIN registry.observations o ON o.file_id=b.file_id
                WHERE o.is_current=1 AND o.status='VERIFIED'
            ) WHERE rank=1 ORDER BY source_date
        """).fetchall()
        predicted = {}
        features = 0
        repaired = 0
        for build, day, value in builds:
            manifest = json.loads(value)
            for product in manifest["products"].values():
                if digest(output / product["path"]) != product["sha256"]:
                    raise ValueError("Product checksum mismatch")
            for name, sha in manifest["source_members"].items():
                path = source / "bronze/data/shp" / ("USDM_" + day.replace("-", "") + "_M") / name
                if digest(path) != sha:
                    raise ValueError("Source checksum mismatch")
            quality = json.loads(
                (output / manifest["products"]["quality"]["path"]).read_text(encoding="utf-8")
            )
            features += quality["silver"]["silver_feature_count"]
            repaired += quality["silver"]["repaired_geometries_count"]
            for time, grid, lon, lat, drought in db.execute(
                "SELECT time,grid,lon,lat,drought FROM gold_cells WHERE build_id=?", (build,)
            ):
                predicted[(time, grid)] = (lon, lat, drought)
    missing = mismatches = matched = 0
    selected = {day.replace("-", "") for _, day, _ in builds}
    with (source / "gold/data/usdmfinal.csv").open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["time"] not in selected:
                continue
            actual = predicted.pop((row["time"], row["grid"]), None)
            if actual is None:
                missing += 1
            elif actual != (float(row["lon"]), float(row["lat"]), row["drought"]):
                mismatches += 1
            else:
                matched += 1
    return {
        "weeks": len(builds),
        "silver_features": features,
        "repaired_geometries": repaired,
        "matched_cells": matched,
        "mismatched_cells": mismatches,
        "missing_cells": missing,
        "extra_cells": len(predicted),
        "source_and_product_hashes_verified": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--registry", required=True, type=Path)
    args = parser.parse_args()
    result = verify(args.source_root, args.output_root, args.registry)
    print(json.dumps(result, indent=2))
    return int(
        not result["weeks"]
        or any(result[key] for key in ["mismatched_cells", "missing_cells", "extra_cells"])
    )


if __name__ == "__main__":
    raise SystemExit(main())
