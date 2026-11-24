"""System routes: liveness and readiness probes."""

from fastapi import APIRouter
from starlette.responses import JSONResponse

from climate_platform.modules.system.readiness import readiness


def system_router() -> APIRouter:
    router = APIRouter()

    @router.get("/livez", tags=["System"])
    async def liveness():
        return {"status": "ok", "service": "climate-data-server"}

    @router.get("/health", tags=["System"], deprecated=True)
    @router.get("/readyz", tags=["System"])
    def health_check():
        ok = readiness.check()
        return JSONResponse(
            {"status": "ok" if ok else "unavailable", "service": "climate-data-server"},
            status_code=200 if ok else 503,
            headers={"Cache-Control": "no-store"},
        )

    return router
