from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict
from starlette.responses import JSONResponse, Response

from .store import token_hash


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str
    password: str


def session_payload(user, config, request_id):
    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "role": user["role"],
        "csrf_token": user["csrf"],
        "demo": config.demo,
        "request_id": request_id,
    }


def auth_router(config, store):
    router = APIRouter()

    @router.get("/auth/info")
    def info():
        accounts = (
            [
                {
                    "username": name,
                    "password": account["password"],
                    "display_name": account["display_name"],
                    "role": account["role"],
                }
                for name, account in config.demo_accounts.items()
            ]
            if config.demo
            else []
        )
        return {"demo": config.demo, "demo_accounts": accounts}

    @router.post("/auth/login")
    def login(request: Request, body: LoginInput):
        token, _ = store.authenticate(body.username, body.password)
        old = request.cookies.get("portal_session")
        if old:
            with store.db() as db:
                db.execute("DELETE FROM sessions WHERE token=?", (token_hash(old),))
        user = store.session(token, config)
        response = JSONResponse(
            session_payload(user, config, request.state.request_id),
            headers={
                "Cache-Control": "private, no-store",
                "X-Request-ID": request.state.request_id,
            },
        )
        response.set_cookie(
            "portal_session",
            token,
            max_age=config.session_max_seconds,
            httponly=True,
            secure=config.secure_cookie,
            samesite="lax",
            path="/",
        )
        return response

    @router.get("/session")
    def session(request: Request):
        user = request.state.portal_user
        return session_payload(user, config, request.state.request_id)

    @router.post("/auth/logout")
    def logout(request: Request):
        with store.db() as db:
            db.execute(
                "DELETE FROM sessions WHERE token=?",
                (token_hash(request.cookies.get("portal_session", "")),),
            )
            store.audit(
                db,
                request.state.portal_user["user_id"],
                "logout",
                None,
                request_id=request.state.request_id,
            )
        response = Response(status_code=204)
        response.delete_cookie("portal_session", path="/")
        return response

    return router
