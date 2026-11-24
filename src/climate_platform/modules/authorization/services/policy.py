"""Authorization policy: who may do what (role, dataset grants, allowed upload sources)."""

from climate_platform.common.errors import PortalError
from climate_platform.config import settings


def allowed_sources(client_id):
    for record in settings.API_KEYS:
        if record.client_id == client_id:
            return record.sources if record.role == "collector" else set()
    return {
        "collector01": settings.COLLECTOR_SOURCES,
        "client01": {"usdm", "noaa"},
        "client02": {"usgs", "nldas"},
    }.get(client_id, set())


def readable_grants(store, user_id, dataset_id, layer=None, action="read"):
    grants = store.actions(user_id, dataset_id)
    readable = {k: v for k, v in grants.items() if "read" in v}
    if not readable or (layer and layer not in readable):
        raise PortalError(404, "RESOURCE_NOT_FOUND")
    if layer and action not in readable[layer]:
        raise PortalError(403, "ACTION_FORBIDDEN")
    return readable


def require_admin(user):
    if user["role"] != "Admin":
        raise PortalError(403, "ACTION_FORBIDDEN")
