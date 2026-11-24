"""Portal selection service: create a selection and read its layers.

One job: orchestrate selection creation and the read endpoints (preview/schema/quality/
lineage/map) from the resolved layer projections. Downloads are delegated to
``services.download``; permissions come from the authorization policy.
"""

import json
import time

from climate_platform.modules.authorization.services.policy import readable_grants
from climate_platform.modules.portal.errors import PortalError
from climate_platform.modules.portal.services.download import download as download_artifact
from climate_platform.modules.portal.services.layers import (
    LAYERS,
    artifact_list,
    layer_status,
    table,
)
from climate_platform.modules.portal.services.pagination import paginate
from climate_platform.modules.portal.services.release import release
from climate_platform.modules.portal.services.resolution import selected
from climate_platform.modules.portal.workers.reader import bounded_read


class SelectionService:
    def __init__(self, store, config):
        self.store = store
        self.config = config

    def create(self, user_id, ctx, body):
        grants = readable_grants(self.store, user_id, body.dataset_id)
        rel = release(self.store, self.config, body.release_id)
        if (
            body.mode not in {"current", "history"}
            or (body.mode == "current" and body.version_id)
            or (body.mode == "history" and not body.version_id)
        ):
            raise PortalError(422, "VERSION_MISMATCH")
        if body.mode == "history":
            version = self.store.resolve(body.version_id, "version", user_id)
            if any(version[k] != getattr(body, k) for k in ["release_id", "dataset_id", "week"]):
                raise PortalError(422, "VERSION_MISMATCH")
            observations = [
                o
                for o in rel.observations(body.dataset_id, False)
                if o["file_id"] == version["file_id"]
            ]
        else:
            version = None
            observations = [
                o for o in rel.observations(body.dataset_id) if o["source_date"] == body.week
            ]
        if len(observations) != 1:
            raise PortalError(404, "RESOURCE_NOT_FOUND")
        obs = observations[0]
        build = rel.catalog["builds"].get(version["build_id"]) if version else rel.latest(obs)
        selection = {
            "release_id": rel.rid,
            "dataset_id": body.dataset_id,
            "week": body.week,
            "file_id": obs["file_id"],
            "build_id": build["build_id"] if build else None,
            "mode": body.mode,
            "expires_at": time.time() + self.config.selection_seconds,
        }
        sid = self.store.transient("selection", user_id, selection, self.config.selection_seconds)
        artifacts = artifact_list(rel, obs, build)
        layers = {}
        for layer in grants:
            status = layer_status(rel, obs, build, layer)
            item = artifacts.get(layer)
            layers[layer] = {
                "availability": status,
                "reason_code": None
                if status == "available"
                else ("LAYER_NOT_BUILT" if status == "not_built" else "ARTIFACT_UNAVAILABLE"),
                "verification": ("bytes_verified" if layer == "bronze" else "quality_passed")
                if status == "available"
                else "unknown",
                "capabilities": {
                    "table": True,
                    "map": layer != "bronze",
                    "schema": True,
                    "quality": True,
                    "lineage": True,
                    "download": "download" in grants[layer],
                },
                "artifacts": [
                    {k: v for k, v in item.items() if k != "path"}
                    | {"download_allowed": "download" in grants[layer]}
                ]
                if item
                else [],
            }
        return {
            "selection_id": sid,
            **{k: v for k, v in selection.items() if k not in {"file_id", "build_id"}},
            "file_id": obs["file_id"] if "bronze" in grants else None,
            "build_id": selection["build_id"]
            if any(layer_name in grants for layer_name in ["silver", "gold"])
            else None,
            "revision": obs["revision"],
            "layers": layers,
            "as_of": rel.info["as_of"],
            "request_id": ctx.request_id,
        }

    def preview(self, user_id, ctx, sid, layer):
        _, rel, obs, build, _ = selected(self.store, self.config, ctx, user_id, sid, layer)
        rows, columns = table(rel, obs, build, layer, ctx)
        result = paginate(self.store, user_id, ctx, rows, rel.rid, 50, 200)
        result.update(
            rows=result.pop("items"),
            columns=columns,
            matched_count=len(rows),
            selection_id=sid,
            revision=obs["revision"],
        )
        if len(json.dumps(result).encode()) > 1024 * 1024:
            raise PortalError(413, "PREVIEW_TOO_LARGE")
        return result

    def schema(self, user_id, ctx, sid, layer):
        _, rel, obs, build, _ = selected(self.store, self.config, ctx, user_id, sid, layer)
        _, fields = table(rel, obs, build, layer, ctx)
        return {
            "fields": fields,
            "crs": "EPSG:4326" if layer != "bronze" else None,
            "selection_id": sid,
            "release_id": rel.rid,
        }

    def quality(self, user_id, ctx, sid, layer):
        _, rel, obs, build, _ = selected(self.store, self.config, ctx, user_id, sid, layer)
        result = (
            {
                "verification": "bytes_verified",
                "scientific_validation": "not_assessed",
                "size_bytes": obs["size_bytes"],
                "sha256": obs["sha256"],
            }
            if layer == "bronze"
            else build["quality"][layer]
        )
        return {
            "metrics": result,
            "selection_id": sid,
            "release_id": rel.rid,
            "checked_at": build["completed_at"] if layer != "bronze" else obs["received_at"],
        }

    def lineage(self, user_id, ctx, sid, layer):
        _, rel, obs, build, grants = selected(self.store, self.config, ctx, user_id, sid, layer)
        nodes = []
        for current in LAYERS:
            if current not in grants:
                nodes.append(
                    {"layer": current, "restricted": True, "label": "Nguồn phụ thuộc bị giới hạn"}
                )
            else:
                item = artifact_list(rel, obs, build).get(current)
                nodes.append(
                    {
                        "layer": current,
                        "id": obs["file_id"]
                        if current == "bronze"
                        else build["build_id"]
                        if build
                        else None,
                        "sha256": item["sha256"] if item else None,
                        "restricted": False,
                    }
                )
        return {
            "nodes": nodes,
            "edges": [["bronze", "silver"], ["silver", "gold"]],
            "recipe": build["recipe"] if build and layer != "bronze" else None,
            "selection_id": sid,
            "release_id": rel.rid,
        }

    def map_data(self, user_id, ctx, sid, layer, bbox, zoom, drought):
        _, rel, obs, build, _ = selected(self.store, self.config, ctx, user_id, sid, layer)
        if layer == "bronze":
            raise PortalError(422, "MAP_NOT_SUPPORTED")
        try:
            west, south, east, north = map(float, bbox.split(","))
            if not (-180 <= west < east <= 180 and -90 <= south < north <= 90 and 0 <= zoom <= 12):
                raise ValueError()
        except ValueError:
            raise PortalError(422, "INVALID_FILTER") from None
        if drought and drought not in (
            ["D0", "D1", "D2", "D3", "D4"]
            if layer == "silver"
            else ["0", "D0", "D1", "D2", "D3", "D4"]
        ):
            raise PortalError(422, "INVALID_FILTER")
        job = {
            "operation": "map",
            "layer": layer,
            "bbox": [west, south, east, north],
            "drought": drought,
            "selection_id": sid,
            "release_id": rel.rid,
        }
        if layer == "silver":
            level = 0 if zoom < 5 else 1 if zoom < 8 else 2
            job["path"] = str(rel.verified(f"serving/{build['build_id']}/map-{level}.json"))
        else:
            job["rows"], _ = table(rel, obs, build, layer, ctx)
        return bounded_read(job)

    def download(self, user_id, ctx, sid, aid):
        return download_artifact(self.store, self.config, user_id, ctx, sid, aid)
