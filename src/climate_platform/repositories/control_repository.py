"""Portal control store (SQLite): transient/usage/leases/audit/config only.

Users/sessions live in ``repositories.auth_repository`` and grants in
``repositories.authorization_repository``; this store composes those repositories so
request handling keeps a single facade.

Statements are ORM constructs; ``BEGIN IMMEDIATE`` (writer serialization) stays an explicit
driver call because it is transaction control, not a query.
"""

import json
import secrets
import time
from contextlib import contextmanager

from sqlalchemy import case, delete, func, insert, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from climate_platform.common.errors import PortalError
from climate_platform.entity.control import (
    Audit,
    Config,
    ControlBase,
    Lease,
    PortalUsage,
    Transient,
)
from climate_platform.repositories.authorization_repository import GrantRepository
from climate_platform.repositories.auth_repository import (
    SessionRepository,
    UserRepository,
    token_hash,
)
from climate_platform.repositories.database import connection, engine_for


class Store:
    # Writers still serialize on one SQLite file; a longer busy wait absorbs short bursts
    # (high Portal concurrency) instead of surfacing a 503 after only 2s.
    BUSY_TIMEOUT_SECONDS = 5

    def __init__(self, root):
        self.root = root
        self.path = root / "control.sqlite3"
        self.users = UserRepository(self)
        self.sessions = SessionRepository(self)
        self.grants = GrantRepository(self)

    def initialize(self):
        self.root.mkdir(parents=True, exist_ok=True)
        timeout = self.BUSY_TIMEOUT_SECONDS
        engine_for(self.path, mode="rwc", busy_timeout=timeout)
        ControlBase.metadata.create_all(engine_for(self.path, mode="rwc", busy_timeout=timeout))

    @contextmanager
    def db(self, create=False):
        with connection(
            self.path, mode="rwc" if create else "rw", busy_timeout=self.BUSY_TIMEOUT_SECONDS
        ) as db:
            yield db
            db.commit()

    @contextmanager
    def write(self):
        """Writer unit of work: opens the store and starts ``BEGIN IMMEDIATE``."""
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            yield db

    def list_audit(self, limit=1000):
        with self.db() as db:
            return [
                dict(r)
                for r in db.execute(
                    select(Audit)
                    .order_by(Audit.timestamp.desc(), Audit.event_id.desc())
                    .limit(limit)
                ).mappings()
            ]

    def active_release(self):
        with self.db() as db:
            row = (
                db.execute(select(Config.value).where(Config.key == "active_release"))
                .mappings()
                .first()
            )
        return row["value"] if row else None

    def audit(self, db, actor, action, target, result="ok", request_id=None):
        db.execute(
            insert(Audit).values(
                timestamp=time.time(),
                actor=actor,
                action=action,
                target=target,
                result=result,
                request_id=request_id,
            )
        )

    def record_audit(self, actor, action, target, result="ok", request_id=None):
        """Write a single audit event in its own committed transaction."""
        with self.db() as db:
            self.audit(db, actor, action, target, result, request_id)

    def transient(self, kind, user, data, ttl=900):
        token = secrets.token_urlsafe(32)
        with self.db() as db:
            db.execute(delete(Transient).where(Transient.expires < time.time()))
            if kind == "selection":
                count = db.execute(
                    select(func.count())
                    .select_from(Transient)
                    .where(Transient.kind == kind, Transient.user_id == user)
                ).scalar_one()
                if count >= 20:
                    # Evict oldest selections, never overwrite a selected release/build.
                    oldest = (
                        select(Transient.token)
                        .where(Transient.kind == kind, Transient.user_id == user)
                        .order_by(Transient.expires)
                        .limit(1)
                        .scalar_subquery()
                    )
                    db.execute(delete(Transient).where(Transient.token.in_(oldest)))
            db.execute(
                insert(Transient).values(
                    token=token_hash(token),
                    kind=kind,
                    user_id=user,
                    data=json.dumps(data),
                    expires=time.time() + ttl,
                )
            )
        return token

    def resolve(self, token, kind, user, consume=False):
        hashed = token_hash(token)
        with self.db() as db:
            if consume:
                db.execute("BEGIN IMMEDIATE")
            row = (
                db.execute(
                    select(Transient).where(
                        Transient.token == hashed,
                        Transient.kind == kind,
                        Transient.user_id == user,
                    )
                )
                .mappings()
                .first()
            )
            if not row:
                raise PortalError(404, "RESOURCE_NOT_FOUND")
            if row["expires"] < time.time():
                raise PortalError(410, "SELECTION_EXPIRED")
            if consume:
                db.execute(delete(Transient).where(Transient.token == hashed))
            return json.loads(row["data"])

    def limit(self, uid, category):
        """Per-minute counter as a single atomic upsert; no ``BEGIN IMMEDIATE`` on the hot path.

        The counter increments with one ``INSERT ... ON CONFLICT DO UPDATE ... RETURNING``
        statement (SQLite serializes it), so every request no longer opens a write
        transaction that holds the store lock across a read.
        """
        maximum = {"metadata": 120, "preview": 30}[category]
        minute = int(time.time()) // 60
        with self.db() as db:
            row = (
                db.execute(
                    select(PortalUsage.minute, PortalUsage.count).where(
                        PortalUsage.user_id == uid, PortalUsage.category == category
                    )
                )
                .mappings()
                .first()
            )
            if row and row["minute"] == minute and row["count"] >= maximum:
                raise PortalError(429, "RATE_LIMITED")
            count = db.execute(
                sqlite_insert(PortalUsage)
                .values(user_id=uid, category=category, minute=minute, count=1)
                .on_conflict_do_update(
                    index_elements=[PortalUsage.user_id, PortalUsage.category],
                    set_={
                        "minute": minute,
                        "count": case(
                            (PortalUsage.minute == minute, PortalUsage.count + 1),
                            else_=1,
                        ),
                    },
                )
                .returning(PortalUsage.count)
            ).scalar_one()
        if count > maximum:
            raise PortalError(429, "RATE_LIMITED")

    def acquire(self, uid, category, limit, ttl):
        lease = secrets.token_hex(16)
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(delete(Lease).where(Lease.expires < time.time()))
            count = db.execute(
                select(func.count())
                .select_from(Lease)
                .where(Lease.user_id == uid, Lease.category == category)
            ).scalar_one()
            if count >= limit:
                raise PortalError(429, "RATE_LIMITED")
            db.execute(
                insert(Lease).values(
                    lease_id=lease, user_id=uid, category=category, expires=time.time() + ttl
                )
            )
        return lease

    def release(self, lease):
        with self.db() as db:
            db.execute(delete(Lease).where(Lease.lease_id == lease))

    # Facade delegating to the auth/authorization repositories (SQL lives there).
    def create_user(self, *args, **kwargs):
        return self.users.create_user(*args, **kwargs)

    def ensure_user(self, *args, **kwargs):
        return self.users.ensure_user(*args, **kwargs)

    def ensure_bootstrap(self, *args, **kwargs):
        return self.users.ensure_bootstrap(*args, **kwargs)

    def authenticate(self, *args, **kwargs):
        return self.sessions.authenticate(*args, **kwargs)

    def start_session(self, *args, **kwargs):
        return self.sessions.start_session(*args, **kwargs)

    def session(self, *args, **kwargs):
        return self.sessions.session(*args, **kwargs)

    def actions(self, *args, **kwargs):
        return self.grants.actions(*args, **kwargs)


__all__ = ["Store", "token_hash"]
