"""Portal catalog routes (thin: delegate to :class:`CatalogService`)."""

from fastapi import APIRouter, Request

from climate_platform.common.pipes import request_ctx


def catalog_controller(service):
    router = APIRouter()

    def uid(request):
        return request.state.portal_user["user_id"]

    @router.get("/sources")
    def sources(request: Request):
        return service.sources(uid(request), request_ctx(request))

    @router.get("/datasets")
    def datasets(request: Request):
        return service.datasets(uid(request), request_ctx(request))

    @router.get("/overview")
    def overview(request: Request):
        return service.overview(uid(request), request_ctx(request))

    @router.get("/datasets/{did}")
    def dataset(request: Request, did: str):
        return service.dataset(uid(request), request_ctx(request), did)

    @router.get("/datasets/{did}/weeks")
    def weeks(request: Request, did: str):
        return service.weeks(uid(request), request_ctx(request), did)

    @router.get("/datasets/{did}/weeks/{week}/versions")
    def versions(request: Request, did: str, week: str):
        return service.versions(uid(request), request_ctx(request), did, week)

    @router.get("/datasets/{did}/attempts")
    def attempts(request: Request, did: str):
        user = request.state.portal_user
        return service.attempts(user["user_id"], user["role"], request_ctx(request), did)

    return router
