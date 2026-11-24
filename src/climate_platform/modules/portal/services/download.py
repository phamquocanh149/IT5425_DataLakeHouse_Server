"""Portal artifact download: verify bytes, lease, stream and audit.

One job: serve one artifact as a verified byte stream. The service resolves the selection,
enforces the download grant, checks size/range policy, verifies the on-disk checksum under a
lease, and returns the stream plus the HTTP headers. The controller wraps it in the
``StreamingResponse``.
"""

import hashlib
import time
from dataclasses import dataclass

from climate_platform.common.fs import contained
from climate_platform.modules.authorization.services.policy import readable_grants
from climate_platform.modules.portal.errors import PortalError
from climate_platform.modules.portal.services.layers import FORMAT_MEDIA, artifact_list
from climate_platform.modules.portal.services.resolution import selected


@dataclass
class DownloadResult:
    chunks: object
    media_type: str
    headers: dict


def download(store, config, user_id, ctx, sid, aid):
    layer = "bronze" if aid.startswith("raw_") else aid.split("_")[0]
    selection, rel, obs, build, _ = selected(store, config, ctx, user_id, sid, layer)
    readable_grants(store, user_id, selection["dataset_id"], layer, "download")
    item = artifact_list(rel, obs, build).get(layer)
    if not item or item["artifact_id"] != aid:
        raise PortalError(404, "RESOURCE_NOT_FOUND")
    if ctx.headers.get("range"):
        raise PortalError(416, "RANGE_NOT_SUPPORTED")
    if item["size_bytes"] > 128 * 1024 * 1024:
        raise PortalError(413, "DOWNLOAD_TOO_LARGE")
    lease = store.acquire(user_id, "download", 2, 65)
    try:
        path = contained(rel.path, item["path"])
        stream = path.open("rb")
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
    actor = user_id
    store.record_audit(actor, "download_started", aid, request_id=ctx.request_id)

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
            store.record_audit(
                actor,
                "download_completed" if complete else "download_canceled",
                aid,
                request_id=ctx.request_id,
            )

    name = f"USDM_{obs['source_date']}_{layer}_r{obs['revision']}.{item['format']}"
    return DownloadResult(
        chunks=chunks(),
        media_type=FORMAT_MEDIA[item["format"]],
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "Content-Length": str(item["size_bytes"]),
            "X-Content-SHA256": item["sha256"],
        },
    )
