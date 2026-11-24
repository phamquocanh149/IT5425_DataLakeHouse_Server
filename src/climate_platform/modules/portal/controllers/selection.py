"""Portal selection routes (thin: delegate to :class:`SelectionService`)."""

from fastapi import APIRouter, Request
from starlette.responses import StreamingResponse

from climate_platform.common.pipes import request_ctx
from climate_platform.modules.portal.dto import SelectionInput


def selection_controller(service):
    router = APIRouter()

    def uid(request):
        return request.state.portal_user["user_id"]

    @router.post("/selections", status_code=201)
    def select(request: Request, body: SelectionInput):
        return service.create(uid(request), request_ctx(request), body)

    @router.get("/selections/{sid}/layers/{layer}/preview")
    def preview(request: Request, sid: str, layer: str):
        return service.preview(uid(request), request_ctx(request), sid, layer)

    @router.get("/selections/{sid}/layers/{layer}/schema")
    def schema(request: Request, sid: str, layer: str):
        return service.schema(uid(request), request_ctx(request), sid, layer)

    @router.get("/selections/{sid}/layers/{layer}/quality")
    def quality(request: Request, sid: str, layer: str):
        return service.quality(uid(request), request_ctx(request), sid, layer)

    @router.get("/selections/{sid}/layers/{layer}/lineage")
    def lineage(request: Request, sid: str, layer: str):
        return service.lineage(uid(request), request_ctx(request), sid, layer)

    @router.get("/selections/{sid}/layers/{layer}/map")
    def map_data(
        request: Request,
        sid: str,
        layer: str,
        bbox: str = "-125,24,-66,50",
        zoom: int = 3,
        drought: str | None = None,
    ):
        return service.map_data(uid(request), request_ctx(request), sid, layer, bbox, zoom, drought)

    @router.get("/selections/{sid}/artifacts/{aid}/download")
    def download(request: Request, sid: str, aid: str):
        result = service.download(uid(request), request_ctx(request), sid, aid)
        return StreamingResponse(
            result.chunks, media_type=result.media_type, headers=result.headers
        )

    return router
