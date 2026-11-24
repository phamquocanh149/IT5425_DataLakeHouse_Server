"""Portal release access facade."""

from climate_platform.modules.portal.errors import PortalError
from climate_platform.repositories.releases import Release


def release(store, config, rid=None):
    if not rid:
        rid = store.active_release()
        if not rid:
            raise PortalError(503, "STORAGE_UNAVAILABLE")
    return Release(config.storage_root, rid)


def data(store, config, ctx, user_id):
    cursor = ctx.params.get("cursor")
    rid = ctx.params.get("release_id")
    if cursor:
        item = store.resolve(cursor, "cursor", user_id)
        if rid and rid != item["release_id"]:
            raise PortalError(400, "INVALID_CURSOR")
        rid = item["release_id"]
    return release(store, config, rid)
