"""Portal module: mount Portal routes (opt-in) in the existing app, or a loopback demo."""

import secrets

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import FileResponse, JSONResponse, RedirectResponse
from starlette.staticfiles import StaticFiles

from climate_platform.modules.auth.module import auth_routers
from climate_platform.modules.portal.controllers.admin import admin_controller
from climate_platform.modules.portal.controllers.catalog import catalog_controller
from climate_platform.modules.portal.controllers.selection import selection_controller
from climate_platform.modules.portal.errors import PortalError, error_response
from climate_platform.modules.portal.middleware import PREFIX, portal_access
from climate_platform.modules.portal.services.admin import AdminService
from climate_platform.modules.portal.services.catalog import CatalogService
from climate_platform.modules.portal.services.selection import SelectionService
from climate_platform.repositories.control_repository import Store


def install_portal(app, config):
    store = Store(config.storage_root)
    store.initialize()
    store.ensure_bootstrap(config.bootstrap_username, config.bootstrap_password)
    app.state.portal_config = config
    app.state.portal_store = store

    @app.exception_handler(PortalError)
    async def handle_portal_error(request: Request, exc: PortalError):
        return error_response(exc, getattr(request.state, "request_id", secrets.token_hex(8)))

    previous_validation = app.exception_handlers.get(RequestValidationError)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc):
        if request.url.path.startswith(PREFIX):
            return error_response(PortalError(422, "INVALID_FILTER"), request.state.request_id)
        if previous_validation:
            return await previous_validation(request, exc)
        return JSONResponse({"detail": "Invalid request"}, status_code=422)

    app.middleware("http")(portal_access(config, store))

    for router in auth_routers(config, store):
        app.include_router(router, prefix=PREFIX)
    app.include_router(catalog_controller(CatalogService(store, config)), prefix=PREFIX)
    app.include_router(selection_controller(SelectionService(store, config)), prefix=PREFIX)
    app.include_router(admin_controller(AdminService(store, config)), prefix=PREFIX)

    assets = config.frontend_root / "assets"
    if assets.exists():
        app.mount("/portal/assets", StaticFiles(directory=assets), name="portal-assets")

    @app.get("/portal", include_in_schema=False)
    def portal_redirect():
        return RedirectResponse("/portal/")

    @app.get("/portal/{route:path}", include_in_schema=False)
    def portal_shell(route: str):
        path = config.frontend_root / "index.html"
        if not path.is_file():
            raise PortalError(503, "FRONTEND_NOT_BUILT")
        return FileResponse(path)

    return store
