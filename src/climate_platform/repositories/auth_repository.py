"""SQLAlchemy repositories for Portal users and sessions (``control.sqlite3``)."""

import hashlib
import secrets
import time

from sqlalchemy import delete, insert, select, update

from climate_platform.common.errors import PortalError
from climate_platform.common.security import hash_password, verify_password
from climate_platform.entity import control as _control  # noqa: F401  (populate metadata)
from climate_platform.entity.control import PortalSession, User


def token_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


_DUMMY_HASH = None


def _dummy_password_hash():
    """Lazily built throwaway hash so an unknown user costs the same PBKDF2 work as a real one."""
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password(secrets.token_urlsafe(32))
    return _DUMMY_HASH


class UserRepository:
    def __init__(self, store):
        self.store = store

    def create_user(self, username, password, display_name, role="Viewer", enabled=True):
        with self.store.db() as db:
            db.execute("BEGIN IMMEDIATE")
            if self._by_username(db, username) is not None:
                raise PortalError(409, "USER_EXISTS")
            user = self.insert(db, username, password, display_name, role, enabled)
        return user

    def ensure_user(self, username, password, display_name, role="Viewer", enabled=True):
        with self.store.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self._by_username(db, username)
            if row is not None:
                return dict(row)
            return self.insert(db, username, password, display_name, role, enabled)

    def insert(self, db, username, password, display_name, role, enabled):
        uid = "u_" + secrets.token_hex(12)
        db.execute(
            insert(User).values(
                user_id=uid,
                username=username,
                display_name=display_name[:120],
                role=role,
                enabled=int(enabled),
                password_hash=hash_password(password),
            )
        )
        self.store.audit(db, uid, "account_created", uid)
        return dict(self._by_user_id(db, uid))

    def ensure_bootstrap(self, username, password):
        if not username or not password:
            return
        with self.store.db() as db:
            db.execute("BEGIN IMMEDIATE")
            if self._by_username(db, username) is None:
                self.insert(db, username, password, username, "Admin", True)

    def _by_username(self, db, username):
        return db.execute(select(User).where(User.username == username)).mappings().first()

    def _by_user_id(self, db, user_id):
        return db.execute(select(User).where(User.user_id == user_id)).mappings().first()

    def get(self, db, user_id):
        return self._by_user_id(db, user_id)

    def list_users(self):
        with self.store.db() as db:
            return [
                dict(r) for r in db.execute(select(User).order_by(User.user_id)).mappings().all()
            ]

    def set_password(self, db, target, password):
        db.execute(
            update(User)
            .where(User.user_id == target)
            .values(password_hash=hash_password(password), version=User.version + 1)
        )

    def set_role_enabled(self, db, target, role, enabled):
        db.execute(
            update(User)
            .where(User.user_id == target)
            .values(role=role, enabled=int(enabled), version=User.version + 1)
        )


class SessionRepository:
    def __init__(self, store):
        self.store = store

    def authenticate(self, username, password):
        with self.store.db() as db:
            row = db.execute(select(User).where(User.username == username)).mappings().first()
        user = dict(row) if row is not None else None
        # Always verify against a stored hash (real or a dummy of equal cost) so an unknown
        # or disabled username does not return measurably faster — no timing username oracle.
        stored = user["password_hash"] if user and user["enabled"] else _dummy_password_hash()
        matched = verify_password(password, stored)
        if not user or not user["enabled"] or not matched:
            raise PortalError(401, "INVALID_CREDENTIALS")
        return self.start_session(user["user_id"]), user

    def start_session(self, user_id):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with self.store.db() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute(select(User.user_id).where(User.user_id == user_id)).first():
                raise PortalError(401, "SESSION_REQUIRED")
            db.execute(
                insert(PortalSession).values(
                    token=token_hash(token),
                    user_id=user_id,
                    csrf=csrf,
                    created=time.time(),
                    last_used=time.time(),
                )
            )
            self.store.audit(db, user_id, "login", user_id)
        return token

    def session(self, token, config):
        if not token:
            raise PortalError(401, "SESSION_REQUIRED")
        hashed = token_hash(token)
        now = time.time()
        with self.store.db() as db:
            row = (
                db.execute(
                    select(
                        User,
                        PortalSession.csrf,
                        PortalSession.created,
                        PortalSession.last_used,
                    )
                    .join(PortalSession, PortalSession.user_id == User.user_id)
                    .where(PortalSession.token == hashed)
                )
                .mappings()
                .first()
            )
            if (
                not row
                or not row["enabled"]
                or now - row["last_used"] > config.session_idle_seconds
                or now - row["created"] > config.session_max_seconds
            ):
                raise PortalError(401, "SESSION_REQUIRED")
            # Refresh the sliding idle clock at most every ``session_touch_seconds`` so a
            # busy Portal does not issue one serialized write per request.
            touch_after = getattr(config, "session_touch_seconds", 60)
            if now - row["last_used"] >= touch_after:
                db.execute(
                    update(PortalSession).where(PortalSession.token == hashed).values(last_used=now)
                )
            return dict(row)

    def delete(self, token):
        with self.store.db() as db:
            db.execute(delete(PortalSession).where(PortalSession.token == token_hash(token)))

    def delete_for_user(self, db, user_id):
        """Revoke every session of ``user_id`` inside the caller's write transaction."""
        db.execute(delete(PortalSession).where(PortalSession.user_id == user_id))

    def revoke_user(self, user_id):
        """Revoke every session of ``user_id`` in its own committed transaction."""
        with self.store.write() as db:
            self.delete_for_user(db, user_id)
