"""Portal admin routes (thin: delegate to :class:`AdminService`)."""

from fastapi import APIRouter, Request

from climate_platform.common.pipes import request_ctx
from climate_platform.modules.auth.dto import UserInput
from climate_platform.modules.authorization.dto import GrantInput
from climate_platform.modules.authorization.services.policy import require_admin
from climate_platform.modules.portal.dto import CreateUserInput, PasswordInput


def admin_controller(service):
    router = APIRouter()

    def uid(request):
        return request.state.portal_user["user_id"]

    def guard(request):
        require_admin(request.state.portal_user)

    @router.get("/admin/users")
    def users(request: Request):
        guard(request)
        return service.list_users(uid(request), request_ctx(request))

    @router.post("/admin/users", status_code=201)
    def create_user(request: Request, body: CreateUserInput):
        guard(request)
        return service.create_user(uid(request), request_ctx(request), body)

    @router.put("/admin/users/{target}/password", status_code=204)
    def set_password(request: Request, target: str, body: PasswordInput):
        guard(request)
        service.set_password(uid(request), request_ctx(request), target, body)

    @router.get("/admin/datasets")
    def admin_datasets(request: Request):
        guard(request)
        return service.datasets(uid(request), request_ctx(request))

    @router.patch("/admin/users/{target}")
    def update_user(request: Request, target: str, body: UserInput):
        guard(request)
        return service.update_user(uid(request), request_ctx(request), target, body)

    @router.get("/admin/users/{target}/grants")
    def grants(request: Request, target: str):
        guard(request)
        return service.list_grants(uid(request), request_ctx(request), target)

    @router.put("/admin/users/{target}/grants/{did}/{layer}")
    def set_grant(request: Request, target: str, did: str, layer: str, body: GrantInput):
        guard(request)
        return service.set_grant(uid(request), request_ctx(request), target, did, layer, body)

    @router.delete("/admin/users/{target}/grants/{did}/{layer}", status_code=204)
    def delete_grant(request: Request, target: str, did: str, layer: str):
        guard(request)
        service.delete_grant(uid(request), request_ctx(request), target, did, layer)

    @router.get("/admin/audit")
    def audit(request: Request):
        guard(request)
        return service.list_audit(uid(request), request_ctx(request))

    return router
