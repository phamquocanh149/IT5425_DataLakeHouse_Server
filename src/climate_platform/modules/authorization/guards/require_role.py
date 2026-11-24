"""Guard factory: require one of the given Portal roles (equivalent to @UseGuards)."""

from fastapi import Request

from climate_platform.common.errors import PortalError


def require_role(*roles):
    def dependency(request: Request):
        user = getattr(request.state, "portal_user", None)
        if user is None or user["role"] not in roles:
            raise PortalError(403, "ACTION_FORBIDDEN")
        return user

    return dependency
