"""Authorization module wiring: reusable guards + policy, injectable via Depends."""

from climate_platform.modules.authorization.guards.require_grant import require_grant
from climate_platform.modules.authorization.guards.require_role import require_role
from climate_platform.modules.authorization.guards.require_source import authorize_upload
from climate_platform.modules.authorization.services.policy import (
    allowed_sources,
    readable_grants,
    require_admin,
)

__all__ = [
    "allowed_sources",
    "authorize_upload",
    "readable_grants",
    "require_admin",
    "require_grant",
    "require_role",
]
