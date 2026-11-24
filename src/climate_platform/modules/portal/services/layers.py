"""Portal layer projections: artifact inventory, availability status and table data.

One job: describe a medallion layer for a selected observation/build. Pure read helpers
that resolve artifact metadata, verify availability and extract the previewable table via
the bounded reader worker. No permissions, no leases, no HTTP.
"""

from climate_platform.modules.portal.errors import PortalError
from climate_platform.modules.portal.workers.reader import bounded_read

LAYERS = ("bronze", "silver", "gold")

FORMAT_MEDIA = {
    "zip": "application/zip",
    "parquet": "application/vnd.apache.parquet",
    "csv": "text/csv",
}


def artifact_list(rel, obs, build):
    items = {
        "bronze": {
            "artifact_id": "raw_" + obs["file_id"],
            "path": obs["stored_path"],
            "sha256": obs["sha256"],
            "size_bytes": obs["size_bytes"],
            "format": "zip",
        }
    }
    if build:
        for layer, fmt in [("silver", "parquet"), ("gold", "csv")]:
            items[layer] = {
                "artifact_id": layer + "_" + build["build_id"],
                **build["products"][layer],
                "format": fmt,
            }
    return items


def layer_status(rel, obs, build, layer):
    if obs["status"] != "VERIFIED":
        return "unavailable"
    if layer != "bronze" and not build:
        return "not_built"
    item = artifact_list(rel, obs, build).get(layer)
    try:
        rel.verified(item["path"])
    except (PortalError, OSError):
        return "unavailable"
    return "available"


def table(rel, obs, build, layer, ctx):
    drought = ctx.params.get("drought")
    grid = ctx.params.get("grid")
    if (drought or grid) and layer != "gold":
        raise PortalError(422, "INVALID_FILTER")
    if drought and drought not in ["0", "D0", "D1", "D2", "D3", "D4"]:
        raise PortalError(422, "INVALID_FILTER")
    if grid and len(grid) > 100:
        raise PortalError(422, "INVALID_FILTER")
    if layer == "bronze":
        return obs["members"], [
            {"name": k, "type": "integer" if k == "size_bytes" else "string", "nullable": False}
            for k in ["name", "extension", "size_bytes", "sha256"]
        ]
    if layer == "silver":
        item = bounded_read(
            {
                "operation": "table",
                "path": str(rel.verified(f"serving/{build['build_id']}/table.json")),
            }
        )
        return item["rows"], item["columns"]
    rows = bounded_read(
        {
            "operation": "gold",
            "path": str(rel.verified("products/warehouse.sqlite3")),
            "build": build["build_id"],
            "drought": drought,
            "grid": grid,
        }
    )
    fields = [
        {
            "name": k,
            "type": "number" if k in ["lon", "lat"] else "string",
            "nullable": False,
            "unit": "degrees" if k in ["lon", "lat"] else None,
        }
        for k in ["time", "grid", "lon", "lat", "drought"]
    ]
    return rows, fields
