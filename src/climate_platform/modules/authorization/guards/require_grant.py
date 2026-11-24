"""Guard factory: require a readable grant for the dataset in the request path."""

from fastapi import Request

from climate_platform.modules.authorization.services.policy import readable_grants


def require_grant(layer=None, action="read"):
    def dependency(request: Request):
        store = request.app.state.portal_store
        user = request.state.portal_user
        dataset_id = request.path_params.get("did")
        return readable_grants(store, user["user_id"], dataset_id, layer, action)

    return dependency
