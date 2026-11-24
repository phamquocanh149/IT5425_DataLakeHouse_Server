"""Auth module wiring: authentication + session (controllers, services, guards)."""

from climate_platform.modules.auth.controllers.login import login_router
from climate_platform.modules.auth.controllers.session import session_router
from climate_platform.modules.auth.guards import get_current_client
from climate_platform.modules.auth.services.session import SessionService


def auth_routers(config, store):
    service = SessionService(store, config)
    return [login_router(service), session_router(service)]


def auth_service(store, config):
    return SessionService(store, config)


__all__ = ["auth_routers", "auth_service", "get_current_client"]
