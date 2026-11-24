"""Resolve a stored Portal selection into its release, observation, build and grants.

One job: turn a selection id + layer into the verified collaborators the layer endpoints
need, enforcing read access and layer availability. Shared by the read endpoints and the
download path so the resolution policy lives in exactly one place.
"""

from climate_platform.modules.authorization.services.policy import readable_grants
from climate_platform.modules.portal.errors import PortalError
from climate_platform.modules.portal.services.layers import layer_status
from climate_platform.modules.portal.services.release import release


def selected(store, config, ctx, user_id, sid, layer):
    selection = store.resolve(sid, "selection", user_id)
    grants = readable_grants(store, user_id, selection["dataset_id"], layer)
    rel = release(store, config, selection["release_id"])
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
