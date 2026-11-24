"""Portal catalog business logic: sources, datasets, overview, weeks, versions, attempts.

The controller stays thin: it extracts the request (user, context, path params) and
returns the plain data produced here.
"""

from climate_platform.modules.authorization.services.policy import readable_grants
from climate_platform.modules.portal.errors import PortalError
from climate_platform.modules.portal.services.layers import LAYERS
from climate_platform.modules.portal.services.pagination import date_range, paginate
from climate_platform.modules.portal.services.release import data
from climate_platform.repositories.warehouse_repository import attempts


def visible_datasets(store, ctx, user_id, rel):
    result = []
    q = ctx.params.get("q", "").lower()
    source = ctx.params.get("source")
    layer = ctx.params.get("layer")
    if len(q) > 100 or (source and source not in {"usdm"}) or (layer and layer not in LAYERS):
        raise PortalError(422, "INVALID_FILTER")
    for did, ds in rel.catalog["datasets"].items():
        grants = store.actions(user_id, did)
        layers = [layer_name for layer_name in LAYERS if "read" in grants.get(layer_name, [])]
        if (
            not layers
            or (source and ds["source"] != source)
            or (layer and layer not in layers)
            or q not in (ds["display_name"] + " " + ds["source"]).lower()
        ):
            continue
        observations = date_range(ctx, rel.observations(did), "source_date")
        if not observations:
            continue
        days = [o["source_date"] for o in observations]
        result.append(
            {
                **ds,
                "layers": layers,
                "week_count": len(days),
                "from": min(days),
                "to": max(days),
            }
        )
    return sorted(result, key=lambda d: (d["display_name"], d["dataset_id"]))


class CatalogService:
    def __init__(self, store, config):
        self.store = store
        self.config = config

    def sources(self, user_id, ctx):
        rel = data(self.store, self.config, ctx, user_id)
        names = sorted({d["source"] for d in visible_datasets(self.store, ctx, user_id, rel)})
        return {
            "items": [{"source": s, "partition_kind": "week"} for s in names],
            "release_id": rel.rid,
            "as_of": rel.info["as_of"],
        }

    def datasets(self, user_id, ctx):
        rel = data(self.store, self.config, ctx, user_id)
        return {
            **paginate(
                self.store,
                user_id,
                ctx,
                visible_datasets(self.store, ctx, user_id, rel),
                rel.rid,
            ),
            "as_of": rel.info["as_of"],
        }

    def overview(self, user_id, ctx):
        rel = data(self.store, self.config, ctx, user_id)
        datasets = visible_datasets(self.store, ctx, user_id, rel)
        visible_layers = {layer for ds in datasets for layer in ds["layers"]}
        weeks = gold_rows = silver_features = repairs = 0
        counts = {"bronze": 0, "silver": 0, "gold": 0}
        distributions = {k: 0 for k in ["0", "D0", "D1", "D2", "D3", "D4"]}
        series = []
        for ds in datasets:
            for obs in date_range(ctx, rel.observations(ds["dataset_id"]), "source_date"):
                weeks += 1
                build = rel.latest(obs)
                if obs["status"] != "VERIFIED":
                    continue
                for layer in ds["layers"]:
                    if layer == "bronze" or build:
                        counts[layer] += 1
                if build and "gold" in ds["layers"]:
                    gold_rows += build["counts"]["gold"]
                    row = {"week": obs["source_date"], **build["quality"]["gold"]["counts"]}
                    series.append(row)
                    for key in distributions:
                        distributions[key] += row.get(key, 0)
                if build and "silver" in ds["layers"]:
                    silver_features += build["counts"]["silver"]
                    repairs += build["quality"]["silver"].get("repaired_geometries_count", 0)
        return {
            "datasets": datasets,
            "dataset_count": len(datasets),
            "week_count": weeks,
            "gold_rows": gold_rows if "gold" in visible_layers else None,
            "silver_features": silver_features if "silver" in visible_layers else None,
            "repairs": repairs if "silver" in visible_layers else None,
            "layers": {k: v for k, v in counts.items() if k in visible_layers},
            "distribution": distributions if "gold" in visible_layers else None,
            "series": sorted(series, key=lambda r: r["week"]),
            "release_id": rel.rid,
            "as_of": rel.info["as_of"],
            "request_id": ctx.request_id,
        }

    def dataset(self, user_id, ctx, did):
        rel = data(self.store, self.config, ctx, user_id)
        grants = readable_grants(self.store, user_id, did)
        if did not in rel.catalog["datasets"]:
            raise PortalError(404, "RESOURCE_NOT_FOUND")
        return {
            **rel.catalog["datasets"][did],
            "layers": list(grants),
            "release_id": rel.rid,
            "as_of": rel.info["as_of"],
        }

    def weeks(self, user_id, ctx, did):
        grants = readable_grants(self.store, user_id, did)
        rel = data(self.store, self.config, ctx, user_id)
        rows = []
        for obs in date_range(ctx, rel.observations(did), "source_date"):
            build = rel.latest(obs)
            rows.append(
                {
                    "week": obs["source_date"],
                    "revision": obs["revision"],
                    "layers": {
                        layer_name: (
                            "unavailable"
                            if obs["status"] != "VERIFIED"
                            else "available"
                            if layer_name == "bronze" or build
                            else "not_built"
                        )
                        for layer_name in grants
                    },
                    "gold_rows": build["counts"]["gold"] if build and "gold" in grants else None,
                }
            )
        return {
            **paginate(
                self.store,
                user_id,
                ctx,
                sorted(rows, key=lambda r: r["week"], reverse=True),
                rel.rid,
            ),
            "as_of": rel.info["as_of"],
        }

    def versions(self, user_id, ctx, did, week):
        grants = readable_grants(self.store, user_id, did)
        rel = data(self.store, self.config, ctx, user_id)
        result = []
        for obs in rel.observations(did, False):
            if obs["source_date"] != week:
                continue
            builds = (
                [b for b in rel.catalog["builds"].values() if b["file_id"] == obs["file_id"]]
                if any(layer_name in grants for layer_name in ["silver", "gold"])
                else []
            )
            for build in builds or [None]:
                vid = self.store.transient(
                    "version",
                    user_id,
                    {
                        "release_id": rel.rid,
                        "dataset_id": did,
                        "week": week,
                        "file_id": obs["file_id"],
                        "build_id": build["build_id"] if build else None,
                    },
                )
                latest = rel.latest(obs)
                result.append(
                    {
                        "version_id": vid,
                        "revision": obs["revision"],
                        "build_id": build["build_id"] if build else None,
                        "completed_at": build["completed_at"] if build else obs["received_at"],
                        "is_current": bool(
                            obs["is_current"]
                            and (not build or build["build_id"] == latest["build_id"])
                        ),
                    }
                )
        return paginate(
            self.store,
            user_id,
            ctx,
            sorted(
                result,
                key=lambda r: (r["revision"], r["completed_at"], r["build_id"] or ""),
                reverse=True,
            ),
            rel.rid,
        )

    def attempts(self, user_id, role, ctx, did):
        readable_grants(self.store, user_id, did)
        if role not in {"Operator", "Admin"}:
            raise PortalError(403, "ACTION_FORBIDDEN")
        rel = data(self.store, self.config, ctx, user_id)
        days = {o["source_date"] for o in rel.observations(did, False)}
        items = [
            {
                "attempt_id": r["attempt_id"],
                "date": r["source_date"],
                "status": r["status"],
                "created_at": r["created_at"],
                "safe_reason": "Processing failed; consult operator audit"
                if r["status"] == "failed"
                else None,
            }
            for r in attempts(rel.verified("products/warehouse.sqlite3"), days)
        ]
        return {
            **paginate(self.store, user_id, ctx, date_range(ctx, items, "date"), rel.rid),
            "as_of": rel.info["as_of"],
            "live": False,
        }
