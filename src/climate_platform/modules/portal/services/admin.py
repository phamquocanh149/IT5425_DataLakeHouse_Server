"""Portal admin business logic: users, grants and audit records.

Validation and optimistic-concurrency preconditions live here; every SQL statement and
transaction is issued by the ``Store`` repositories. The controller only delegates.
"""

import json

from climate_platform.modules.portal.dto import CreateUserInput, PasswordInput
from climate_platform.modules.portal.errors import PortalError
from climate_platform.modules.portal.services.layers import LAYERS
from climate_platform.modules.portal.services.pagination import paginate
from climate_platform.modules.portal.services.release import data, release

ROLES = {"Viewer", "Operator", "Admin"}

_USER_COLUMNS = ("user_id", "username", "display_name", "role", "enabled", "version")


def _public_user(row):
    return {key: row[key] for key in _USER_COLUMNS}


class AdminService:
    def __init__(self, store, config):
        self.store = store
        self.config = config

    def list_users(self, user_id, ctx):
        rows = [_public_user(r) for r in self.store.users.list_users()]
        q = ctx.params.get("q", "").lower()
        rows = [r for r in rows if q in r["display_name"].lower() or q in r["username"].lower()]
        return paginate(self.store, user_id, ctx, rows, "admin")

    def create_user(self, actor, ctx, body: CreateUserInput):
        if body.role not in ROLES:
            raise PortalError(422, "INVALID_FILTER")
        user = self.store.create_user(body.username, body.password, body.display_name, body.role)
        self.store.record_audit(actor, "create_user", user["user_id"], request_id=ctx.request_id)
        return {
            "user_id": user["user_id"],
            "username": user["username"],
            "display_name": user["display_name"],
            "role": user["role"],
            "enabled": bool(user["enabled"]),
            "version": user["version"],
        }

    def set_password(self, actor, ctx, target, body: PasswordInput):
        with self.store.write() as db:
            row = self.store.users.get(db, target)
            if row is None:
                raise PortalError(404, "RESOURCE_NOT_FOUND")
            self._precondition(ctx, row)
            self.store.users.set_password(db, target, body.password)
            # Revoke every existing session of the target: a password change/reset must not
            # leave previously-issued sessions valid.
            self.store.sessions.delete_for_user(db, target)
            self.store.audit(db, actor, "password_reset", target, request_id=ctx.request_id)

    def update_user(self, actor, ctx, target, body):
        if target == actor or body.role not in ROLES:
            raise PortalError(403, "ACTION_FORBIDDEN")
        with self.store.write() as db:
            row = self.store.users.get(db, target)
            if row is None:
                raise PortalError(404, "RESOURCE_NOT_FOUND")
            self._precondition(ctx, row)
            self.store.users.set_role_enabled(db, target, body.role, body.enabled)
            if not body.enabled:
                # Disabling an account also revokes its live sessions.
                self.store.sessions.delete_for_user(db, target)
            self.store.audit(db, actor, "update_user", target, request_id=ctx.request_id)
            return _public_user(self.store.users.get(db, target))

    def datasets(self, user_id, ctx):
        rel = data(self.store, self.config, ctx, user_id)
        return paginate(
            self.store,
            user_id,
            ctx,
            [
                {
                    k: v
                    for k, v in d.items()
                    if k in {"dataset_id", "source", "display_name", "layers"}
                }
                for d in rel.catalog["datasets"].values()
            ],
            rel.rid,
        )

    def list_grants(self, user_id, ctx, target):
        rows = self.store.grants.for_user(target)
        for row in rows:
            row["actions"] = json.loads(row["actions"])
        return paginate(self.store, user_id, ctx, rows, "admin")

    def set_grant(self, actor, ctx, target, did, layer, body):
        if (
            layer not in LAYERS
            or not body.actions
            or not set(body.actions) <= {"read", "download"}
            or "read" not in body.actions
        ):
            raise PortalError(422, "INVALID_FILTER")
        if did not in release(self.store, self.config).catalog["datasets"]:
            raise PortalError(404, "RESOURCE_NOT_FOUND")
        with self.store.write() as db:
            if self.store.users.get(db, target) is None:
                raise PortalError(404, "RESOURCE_NOT_FOUND")
            row = self.store.grants.get(db, target, did, layer)
            self._precondition(ctx, row)
            version = row["version"] + 1 if row else 1
            self.store.grants.upsert(db, target, did, layer, body.actions, version)
            self.store.audit(
                db, actor, "grant_updated", f"{target}:{did}:{layer}", request_id=ctx.request_id
            )
        return {
            "user_id": target,
            "dataset_id": did,
            "layer": layer,
            "actions": sorted(set(body.actions)),
            "version": version,
        }

    def delete_grant(self, actor, ctx, target, did, layer):
        with self.store.write() as db:
            row = self.store.grants.get(db, target, did, layer)
            if not row:
                raise PortalError(404, "RESOURCE_NOT_FOUND")
            self._precondition(ctx, row)
            self.store.grants.delete(db, target, did, layer)
            self.store.audit(
                db, actor, "grant_revoked", f"{target}:{did}:{layer}", request_id=ctx.request_id
            )

    def list_audit(self, user_id, ctx):
        return paginate(self.store, user_id, ctx, self.store.list_audit(), "admin")

    def _precondition(self, ctx, row):
        if row is None:
            if ctx.headers.get("if-none-match") != "*":
                raise PortalError(428, "PRECONDITION_REQUIRED")
        elif ctx.headers.get("if-match") is None:
            raise PortalError(428, "PRECONDITION_REQUIRED")
        elif ctx.headers["if-match"].strip('"') != str(row["version"]):
            raise PortalError(412, "VERSION_CONFLICT")
