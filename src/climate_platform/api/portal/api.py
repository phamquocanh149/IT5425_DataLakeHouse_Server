import json
import sqlite3
import time
from contextlib import closing
from datetime import date

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import StreamingResponse

from .releases import Release, contained
from .store import PortalError, hash_password
from .reader import bounded_read

LAYERS = ("bronze", "silver", "gold")


class SelectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: str
    week: str
    release_id: str
    mode: str = "current"
    version_id: str | None = None


class GrantInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actions: list[str]


class UserInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str
    enabled: bool


class CreateUserInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-z0-9._-]+$")
    display_name: str = Field(min_length=1, max_length=120)
    role: str
    password: str = Field(min_length=8, max_length=256)


class PasswordInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=8, max_length=256)


ROLES = {"Viewer", "Operator", "Admin"}


def api_router(config, store):
    router = APIRouter()

    def uid(request):
        return request.state.portal_user["user_id"]

    def release(rid=None):
        if not rid:
            with store.db() as db:
                row = db.execute("SELECT value FROM config WHERE key='active_release'").fetchone()
            if not row:
                raise PortalError(503, "STORAGE_UNAVAILABLE")
            rid = row[0]
        return Release(config.storage_root, rid)

    def allowed(request, did, layer=None, action="read"):
        grants = store.actions(uid(request), did)
        readable = {k: v for k, v in grants.items() if "read" in v}
        if not readable or (layer and layer not in readable):
            raise PortalError(404, "RESOURCE_NOT_FOUND")
        if layer and action not in readable[layer]:
            raise PortalError(403, "ACTION_FORBIDDEN")
        return readable

    def admin(request):
        if request.state.portal_user["role"] != "Admin":
            raise PortalError(403, "ACTION_FORBIDDEN")

    def data(request):
        cursor = request.query_params.get("cursor")
        rid = request.query_params.get("release_id")
        if cursor:
            item = store.resolve(cursor, "cursor", uid(request))
            if rid and rid != item["release_id"]:
                raise PortalError(400, "INVALID_CURSOR")
            rid = item["release_id"]
        return release(rid)

    def paginate(request, items, rid, default=25, maximum=100):
        try:
            limit = int(request.query_params.get("limit", default))
        except ValueError:
            raise PortalError(422, "INVALID_FILTER") from None
        if not 1 <= limit <= maximum:
            raise PortalError(422, "INVALID_FILTER")
        signature = {
            "path": request.url.path,
            "filters": sorted(
                [k, v]
                for k, v in request.query_params.multi_items()
                if k not in {"cursor", "release_id"}
            ),
        }
        offset = 0
        if request.query_params.get("cursor"):
            saved = store.resolve(request.query_params["cursor"], "cursor", uid(request))
            if saved["signature"] != signature or saved["release_id"] != rid:
                raise PortalError(400, "INVALID_CURSOR")
            offset = saved["offset"]
        page = items[offset : offset + limit]
        nxt = None
        if offset + limit < len(items):
            nxt = store.transient(
                "cursor",
                uid(request),
                {"signature": signature, "release_id": rid, "offset": offset + limit},
            )
        return {
            "items": page,
            "page": {"limit": limit, "next_cursor": nxt},
            "release_id": rid,
            "request_id": request.state.request_id,
        }

    def date_range(request, rows, field):
        lower, upper = request.query_params.get("from"), request.query_params.get("to")
        try:
            for value in (lower, upper):
                if value and date.fromisoformat(value).isoformat() != value:
                    raise ValueError()
            if lower and upper and lower > upper:
                raise ValueError()
        except ValueError:
            raise PortalError(422, "INVALID_FILTER") from None
        return [
            r for r in rows if (not lower or r[field] >= lower) and (not upper or r[field] <= upper)
        ]

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

    def visible_datasets(request, rel):
        result = []
        q = request.query_params.get("q", "").lower()
        source = request.query_params.get("source")
        layer = request.query_params.get("layer")
        if len(q) > 100 or (source and source not in {"usdm"}) or (layer and layer not in LAYERS):
            raise PortalError(422, "INVALID_FILTER")
        for did, ds in rel.catalog["datasets"].items():
            grants = store.actions(uid(request), did)
            layers = [layer_name for layer_name in LAYERS if "read" in grants.get(layer_name, [])]
            if (
                not layers
                or (source and ds["source"] != source)
                or (layer and layer not in layers)
                or q not in (ds["display_name"] + " " + ds["source"]).lower()
            ):
                continue
            observations = date_range(request, rel.observations(did), "source_date")
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

    @router.get("/sources")
    def sources(request: Request):
        rel = data(request)
        names = sorted({d["source"] for d in visible_datasets(request, rel)})
        return {
            "items": [{"source": s, "partition_kind": "week"} for s in names],
            "release_id": rel.rid,
            "as_of": rel.info["as_of"],
        }

    @router.get("/datasets")
    def datasets(request: Request):
        rel = data(request)
        return {
            **paginate(request, visible_datasets(request, rel), rel.rid),
            "as_of": rel.info["as_of"],
        }

    @router.get("/overview")
    def overview(request: Request):
        rel = data(request)
        datasets = visible_datasets(request, rel)
        visible_layers = {layer for ds in datasets for layer in ds["layers"]}
        weeks = gold_rows = silver_features = repairs = 0
        counts = {"bronze": 0, "silver": 0, "gold": 0}
        distributions = {k: 0 for k in ["0", "D0", "D1", "D2", "D3", "D4"]}
        series = []
        for ds in datasets:
            for obs in date_range(request, rel.observations(ds["dataset_id"]), "source_date"):
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
            "request_id": request.state.request_id,
        }

    @router.get("/datasets/{did}")
    def dataset(request: Request, did: str):
        rel = data(request)
        grants = allowed(request, did)
        if did not in rel.catalog["datasets"]:
            raise PortalError(404, "RESOURCE_NOT_FOUND")
        return {
            **rel.catalog["datasets"][did],
            "layers": list(grants),
            "release_id": rel.rid,
            "as_of": rel.info["as_of"],
        }

    @router.get("/datasets/{did}/weeks")
    def weeks(request: Request, did: str):
        grants = allowed(request, did)
        rel = data(request)
        rows = []
        for obs in date_range(request, rel.observations(did), "source_date"):
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
            **paginate(request, sorted(rows, key=lambda r: r["week"], reverse=True), rel.rid),
            "as_of": rel.info["as_of"],
        }

    @router.get("/datasets/{did}/weeks/{week}/versions")
    def versions(request: Request, did: str, week: str):
        grants = allowed(request, did)
        rel = data(request)
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
                vid = store.transient(
                    "version",
                    uid(request),
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
            request,
            sorted(
                result,
                key=lambda r: (r["revision"], r["completed_at"], r["build_id"] or ""),
                reverse=True,
            ),
            rel.rid,
        )

    @router.get("/datasets/{did}/attempts")
    def attempts(request: Request, did: str):
        allowed(request, did)
        if request.state.portal_user["role"] not in {"Operator", "Admin"}:
            raise PortalError(403, "ACTION_FORBIDDEN")
        rel = data(request)
        days = {o["source_date"] for o in rel.observations(did, False)}
        with closing(
            sqlite3.connect(
                rel.verified("products/warehouse.sqlite3").as_uri() + "?mode=ro", uri=True
            )
        ) as db:
            db.row_factory = sqlite3.Row
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
                for r in db.execute(
                    "SELECT * FROM attempts ORDER BY created_at DESC,attempt_id DESC"
                )
                if r["source_date"] in days
            ]
        return {
            **paginate(request, date_range(request, items, "date"), rel.rid),
            "as_of": rel.info["as_of"],
            "live": False,
        }

    @router.post("/selections", status_code=201)
    def select(request: Request, body: SelectionInput):
        grants = allowed(request, body.dataset_id)
        rel = release(body.release_id)
        if (
            body.mode not in {"current", "history"}
            or (body.mode == "current" and body.version_id)
            or (body.mode == "history" and not body.version_id)
        ):
            raise PortalError(422, "VERSION_MISMATCH")
        if body.mode == "history":
            version = store.resolve(body.version_id, "version", uid(request))
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
            "expires_at": time.time() + config.selection_seconds,
        }
        sid = store.transient("selection", uid(request), selection, config.selection_seconds)
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
            "request_id": request.state.request_id,
        }

    def selected(request, sid, layer):
        selection = store.resolve(sid, "selection", uid(request))
        grants = allowed(request, selection["dataset_id"], layer)
        rel = release(selection["release_id"])
        obs = next(
            (
                o
                for o in rel.observations(selection["dataset_id"], False)
                if o["file_id"] == selection["file_id"]
            ),
            None,
        )
        if not obs:
            raise PortalError(404, "RESOURCE_NOT_FOUND")
        build = rel.catalog["builds"].get(selection["build_id"])
        status = layer_status(rel, obs, build, layer)
        if status != "available":
            raise PortalError(
                409 if status == "not_built" else 503,
                "LAYER_NOT_BUILT" if status == "not_built" else "ARTIFACT_UNAVAILABLE",
            )
        return selection, rel, obs, build, grants

    def table(rel, obs, build, layer, request):
        drought = request.query_params.get("drought")
        grid = request.query_params.get("grid")
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

    @router.get("/selections/{sid}/layers/{layer}/preview")
    def preview(request: Request, sid: str, layer: str):
        selection, rel, obs, build, _ = selected(request, sid, layer)
        rows, columns = table(rel, obs, build, layer, request)
        result = paginate(request, rows, rel.rid, 50, 200)
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

    @router.get("/selections/{sid}/layers/{layer}/schema")
    def schema(request: Request, sid: str, layer: str):
        _, rel, obs, build, _ = selected(request, sid, layer)
        _, fields = table(rel, obs, build, layer, request)
        return {
            "fields": fields,
            "crs": "EPSG:4326" if layer != "bronze" else None,
            "selection_id": sid,
            "release_id": rel.rid,
        }

    @router.get("/selections/{sid}/layers/{layer}/quality")
    def quality(request: Request, sid: str, layer: str):
        _, rel, obs, build, _ = selected(request, sid, layer)
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

    @router.get("/selections/{sid}/layers/{layer}/lineage")
    def lineage(request: Request, sid: str, layer: str):
        _, rel, obs, build, grants = selected(request, sid, layer)
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

    @router.get("/selections/{sid}/layers/{layer}/map")
    def map_data(
        request: Request,
        sid: str,
        layer: str,
        bbox: str = "-125,24,-66,50",
        zoom: int = 3,
        drought: str | None = None,
    ):
        _, rel, obs, build, _ = selected(request, sid, layer)
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
            job["rows"], _ = table(rel, obs, build, layer, request)
        return bounded_read(job)

    @router.get("/selections/{sid}/artifacts/{aid}/download")
    def download(request: Request, sid: str, aid: str):
        layer = "bronze" if aid.startswith("raw_") else aid.split("_")[0]
        selection, rel, obs, build, _ = selected(request, sid, layer)
        allowed(request, selection["dataset_id"], layer, "download")
        item = artifact_list(rel, obs, build).get(layer)
        if not item or item["artifact_id"] != aid:
            raise PortalError(404, "RESOURCE_NOT_FOUND")
        if request.headers.get("range"):
            raise PortalError(416, "RANGE_NOT_SUPPORTED")
        if item["size_bytes"] > 128 * 1024 * 1024:
            raise PortalError(413, "DOWNLOAD_TOO_LARGE")
        lease = store.acquire(uid(request), "download", 2, 65)
        try:
            path = contained(rel.path, item["path"])
            stream = path.open("rb")
            import hashlib

            if (
                hashlib.file_digest(stream, "sha256").hexdigest() != item["sha256"]
                or path.stat().st_size != item["size_bytes"]
            ):
                stream.close()
                raise PortalError(503, "ARTIFACT_UNAVAILABLE")
            stream.seek(0)
        except Exception:
            store.release(lease)
            raise
        actor = uid(request)
        with store.db() as db:
            store.audit(db, actor, "download_started", aid, request_id=request.state.request_id)

        def chunks():
            complete = False
            deadline = time.monotonic() + 60
            try:
                while True:
                    if time.monotonic() > deadline:
                        return
                    chunk = stream.read(64 * 1024)
                    if not chunk:
                        complete = True
                        break
                    yield chunk
            finally:
                stream.close()
                store.release(lease)
                with store.db() as db:
                    store.audit(
                        db,
                        actor,
                        "download_completed" if complete else "download_canceled",
                        aid,
                        request_id=request.state.request_id,
                    )

        name = f"USDM_{obs['source_date']}_{layer}_r{obs['revision']}.{item['format']}"
        return StreamingResponse(
            chunks(),
            media_type={
                "zip": "application/zip",
                "parquet": "application/vnd.apache.parquet",
                "csv": "text/csv",
            }[item["format"]],
            headers={
                "Content-Disposition": f'attachment; filename="{name}"',
                "Content-Length": str(item["size_bytes"]),
                "X-Content-SHA256": item["sha256"],
            },
        )

    @router.get("/admin/users")
    def users(request: Request):
        admin(request)
        with store.db() as db:
            rows = [
                dict(r)
                for r in db.execute(
                    "SELECT user_id,username,display_name,role,enabled,version FROM users"
                    " ORDER BY user_id"
                )
            ]
        q = request.query_params.get("q", "").lower()
        return paginate(
            request,
            [r for r in rows if q in r["display_name"].lower() or q in r["username"].lower()],
            "admin",
        )

    @router.post("/admin/users", status_code=201)
    def create_user(request: Request, body: CreateUserInput):
        admin(request)
        if body.role not in ROLES:
            raise PortalError(422, "INVALID_FILTER")
        user = store.create_user(body.username, body.password, body.display_name, body.role)
        with store.db() as db:
            store.audit(
                db,
                uid(request),
                "create_user",
                user["user_id"],
                request_id=request.state.request_id,
            )
        return {
            "user_id": user["user_id"],
            "username": user["username"],
            "display_name": user["display_name"],
            "role": user["role"],
            "enabled": bool(user["enabled"]),
            "version": user["version"],
        }

    @router.put("/admin/users/{target}/password", status_code=204)
    def set_password(request: Request, target: str, body: PasswordInput):
        admin(request)
        with store.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM users WHERE user_id=?", (target,)).fetchone()
            if row is None:
                raise PortalError(404, "RESOURCE_NOT_FOUND")
            precondition(request, row)
            db.execute(
                "UPDATE users SET password_hash=?,version=version+1 WHERE user_id=?",
                (hash_password(body.password), target),
            )
            store.audit(
                db,
                uid(request),
                "password_reset",
                target,
                request_id=request.state.request_id,
            )

    @router.get("/admin/datasets")
    def admin_datasets(request: Request):
        admin(request)
        rel = data(request)
        return paginate(
            request,
            [
                {
                    k: v
                    for k, v in d.items()
                    if k in {"dataset_id", "source", "display_name", "layers"}
                }
                for d in rel.catalog["datasets"].values()
            ],
            rel.rid,
        )

    @router.patch("/admin/users/{target}")
    def update_user(request: Request, target: str, body: UserInput):
        admin(request)
        if target == uid(request) or body.role not in ROLES:
            raise PortalError(403, "ACTION_FORBIDDEN")
        with store.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM users WHERE user_id=?", (target,)).fetchone()
            if row is None:
                raise PortalError(404, "RESOURCE_NOT_FOUND")
            precondition(request, row)
            db.execute(
                "UPDATE users SET role=?,enabled=?,version=version+1 WHERE user_id=?",
                (body.role, int(body.enabled), target),
            )
            store.audit(
                db, uid(request), "update_user", target, request_id=request.state.request_id
            )
            return dict(
                db.execute(
                    "SELECT user_id,username,display_name,role,enabled,version FROM users"
                    " WHERE user_id=?",
                    (target,),
                ).fetchone()
            )

    def precondition(request, row):
        if row is None:
            if request.headers.get("if-none-match") != "*":
                raise PortalError(428, "PRECONDITION_REQUIRED")
        elif request.headers.get("if-match") is None:
            raise PortalError(428, "PRECONDITION_REQUIRED")
        elif request.headers["if-match"].strip('"') != str(row["version"]):
            raise PortalError(412, "VERSION_CONFLICT")

    @router.get("/admin/users/{target}/grants")
    def grants(request: Request, target: str):
        admin(request)
        with store.db() as db:
            rows = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM grants WHERE user_id=? ORDER BY dataset_id,layer", (target,)
                )
            ]
        for row in rows:
            row["actions"] = json.loads(row["actions"])
        return paginate(request, rows, "admin")

    @router.put("/admin/users/{target}/grants/{did}/{layer}")
    def set_grant(request: Request, target: str, did: str, layer: str, body: GrantInput):
        admin(request)
        if (
            layer not in LAYERS
            or not body.actions
            or not set(body.actions) <= {"read", "download"}
            or "read" not in body.actions
        ):
            raise PortalError(422, "INVALID_FILTER")
        if did not in release().catalog["datasets"]:
            raise PortalError(404, "RESOURCE_NOT_FOUND")
        with store.db() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT user_id FROM users WHERE user_id=?", (target,)).fetchone():
                raise PortalError(404, "RESOURCE_NOT_FOUND")
            row = db.execute(
                "SELECT * FROM grants WHERE user_id=? AND dataset_id=? AND layer=?",
                (target, did, layer),
            ).fetchone()
            precondition(request, row)
            version = row["version"] + 1 if row else 1
            db.execute(
                "INSERT OR REPLACE INTO grants VALUES (?,?,?,?,?)",
                (target, did, layer, json.dumps(sorted(set(body.actions))), version),
            )
            store.audit(
                db,
                uid(request),
                "grant_updated",
                f"{target}:{did}:{layer}",
                request_id=request.state.request_id,
            )
        return {
            "user_id": target,
            "dataset_id": did,
            "layer": layer,
            "actions": sorted(set(body.actions)),
            "version": version,
        }

    @router.delete("/admin/users/{target}/grants/{did}/{layer}", status_code=204)
    def delete_grant(request: Request, target: str, did: str, layer: str):
        admin(request)
        with store.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM grants WHERE user_id=? AND dataset_id=? AND layer=?",
                (target, did, layer),
            ).fetchone()
            if not row:
                raise PortalError(404, "RESOURCE_NOT_FOUND")
            precondition(request, row)
            db.execute(
                "DELETE FROM grants WHERE user_id=? AND dataset_id=? AND layer=?",
                (target, did, layer),
            )
            store.audit(
                db,
                uid(request),
                "grant_revoked",
                f"{target}:{did}:{layer}",
                request_id=request.state.request_id,
            )

    @router.get("/admin/audit")
    def audit(request: Request):
        admin(request)
        with store.db() as db:
            rows = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM audit ORDER BY timestamp DESC,event_id DESC LIMIT 1000"
                )
            ]
        return paginate(request, rows, "admin")

    return router
