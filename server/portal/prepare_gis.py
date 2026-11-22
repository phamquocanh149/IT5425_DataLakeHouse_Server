"""Offline display indexes. Invoked with a GIS Python; never during an HTTP request."""

import json
import sys
from pathlib import Path


def prepare(root):
    import geopandas as gpd
    import pandas as pd
    from shapely.geometry import mapping

    catalog = json.loads((root / "catalog.json").read_text(encoding="utf-8"))
    for build in catalog["builds"].values():
        artifact = build["products"]["silver"]
        frame = gpd.read_parquet(root / artifact["path"])
        target = root / "serving" / build["build_id"]
        target.mkdir(parents=True, exist_ok=True)
        table = frame.drop(columns="geometry").copy()
        table.insert(0, "row_id", range(len(table)))
        table["geometry_type"] = frame.geom_type
        rows = json.loads(table.to_json(orient="records", date_format="iso"))
        fields = [
            {
                "name": c,
                "type": str(table[c].dtype),
                "nullable": bool(table[c].isna().any()),
                "unit": None,
                "description": "Display row ordinal" if c == "row_id" else c.replace("_", " "),
            }
            for c in table.columns
        ]
        (target / "table.json").write_text(
            json.dumps({"rows": rows, "columns": fields}, ensure_ascii=False), encoding="utf-8"
        )
        for level, tolerance in enumerate([0.05, 0.01, 0.002]):
            features = []
            for ordinal, (_, row) in enumerate(frame.iterrows()):
                geometry = row.geometry.simplify(tolerance, preserve_topology=True)
                features.append(
                    {
                        "type": "Feature",
                        "id": ordinal,
                        "bbox": list(geometry.bounds),
                        "properties": {"row_id": ordinal, "drought": f"D{int(row.dm_value)}"},
                        "geometry": mapping(geometry),
                    }
                )
            (target / f"map-{level}.json").write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": features,
                        "metadata": {"geometry_simplified": True, "tolerance_degrees": tolerance},
                    },
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
        quality = json.loads(
            (root / build["products"]["quality"]["path"]).read_text(encoding="utf-8")
        )
        build["counts"] = {"silver": len(frame), "gold": int(quality["gold_cells"])}
        # Source metric strings may contain operational paths; only publish known fields.
        build["quality"] = {
            "silver": {
                key: value
                for key, value in quality["silver"].items()
                if key not in {"notes", "source_file"}
            },
            "gold": {"gold_cells": quality["gold_cells"], "counts": quality["counts"]},
        }
        if not pd.Series(frame.geometry.is_valid).all():
            raise ValueError("Invalid Silver geometry")
    (root / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    prepare(Path(sys.argv[1]))
