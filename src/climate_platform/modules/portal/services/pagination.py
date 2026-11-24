"""Portal pagination + cursor signature."""

from datetime import date

from climate_platform.modules.portal.errors import PortalError


def paginate(store, user_id, ctx, items, rid, default=25, maximum=100):
    try:
        limit = int(ctx.params.get("limit", default))
    except ValueError:
        raise PortalError(422, "INVALID_FILTER") from None
    if not 1 <= limit <= maximum:
        raise PortalError(422, "INVALID_FILTER")
    signature = {
        "path": ctx.path,
        "filters": sorted([k, v] for k, v in ctx.pairs if k not in {"cursor", "release_id"}),
    }
    offset = 0
    cursor = ctx.params.get("cursor")
    if cursor:
        saved = store.resolve(cursor, "cursor", user_id)
        if saved["signature"] != signature or saved["release_id"] != rid:
            raise PortalError(400, "INVALID_CURSOR")
        offset = saved["offset"]
    page = items[offset : offset + limit]
    nxt = None
    if offset + limit < len(items):
        nxt = store.transient(
            "cursor",
            user_id,
            {"signature": signature, "release_id": rid, "offset": offset + limit},
        )
    return {
        "items": page,
        "page": {"limit": limit, "next_cursor": nxt},
        "release_id": rid,
        "request_id": ctx.request_id,
    }


def date_range(ctx, rows, field):
    lower, upper = ctx.params.get("from"), ctx.params.get("to")
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
