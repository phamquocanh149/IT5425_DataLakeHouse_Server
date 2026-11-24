"""Current-session route (thin: delegate to :class:`SessionService`)."""

from fastapi import APIRouter, Request

from climate_platform.common.pipes import request_ctx


def session_router(service):
    router = APIRouter()

    @router.get("/session")
    def session(request: Request):
        return service.session(request.state.portal_user, request_ctx(request))

    return router
