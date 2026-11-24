"""Auth login/info/logout routes (thin: delegate to :class:`SessionService`)."""

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse, Response

from climate_platform.common.pipes import request_ctx
from climate_platform.modules.auth.dto import LoginInput


def login_router(service):
    router = APIRouter()

    @router.get("/auth/info")
    def info():
        return service.info()

    @router.post("/auth/login")
    def login(request: Request, body: LoginInput):
        ctx = request_ctx(request)
        token, payload = service.login(
            ctx, body.username, body.password, request.cookies.get("portal_session")
        )
        response = JSONResponse(
            payload,
            headers={
                "Cache-Control": "private, no-store",
                "X-Request-ID": ctx.request_id,
            },
        )
        response.set_cookie(
            "portal_session",
            token,
            max_age=service.config.session_max_seconds,
            httponly=True,
            secure=service.config.secure_cookie,
            samesite="lax",
            path="/",
        )
        return response

    @router.post("/auth/logout")
    def logout(request: Request):
        service.logout(
            request_ctx(request),
            request.state.portal_user["user_id"],
            request.cookies.get("portal_session", ""),
        )
        response = Response(status_code=204)
        response.delete_cookie("portal_session", path="/")
        return response

    return router
