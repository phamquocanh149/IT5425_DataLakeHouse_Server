"""Portal pagination + cursor signature."""

from datetime import date

from climate_platform.modules.portal.errors import PortalError


def paginate(store, user_id, request, items, rid, default=25, maximum=100):
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
        saved = store.resolve(request.query_params["cursor"], "cursor", user_id)
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
