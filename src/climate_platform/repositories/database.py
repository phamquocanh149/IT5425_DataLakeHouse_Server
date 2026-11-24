"""SQLAlchemy engine/session plumbing shared by every SQLite repository.

The operational contract stays the same as the previous hand-written ``sqlite3``
layer: a short-lived connection per operation (``NullPool``), WAL with
``synchronous=FULL`` and foreign keys, optional read-only (``mode=ro``) engines,
explicit ``BEGIN IMMEDIATE`` writer transactions, and ``SQLITE_BUSY``/``LOCKED``
mapped to HTTP 503.

Engines use ``isolation_level="AUTOCOMMIT"`` on purpose: repositories keep full
control of transaction boundaries (``BEGIN IMMEDIATE`` / ``COMMIT`` / ``ROLLBACK``)
so SQLite serialization semantics do not change.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from contextlib import closing, contextmanager
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import NullPool

from climate_platform.config import settings

_ENGINES: dict[tuple[str, str, float], object] = {}
_ENGINES_LOCK = threading.Lock()


def _engine_url(path: Path, mode: str) -> str:
    if mode == "rwc":
        return "sqlite:///" + path.as_posix()
    return f"sqlite:///file:{path.as_posix()}?mode={mode}&uri=true"


def engine_for(db_path, *, mode="rw", busy_timeout=None):
    """Return a cached NullPool engine for ``db_path`` in ``rwc``/``rw``/``ro`` mode."""
    path = Path(db_path).resolve()
    timeout = float(settings.SQLITE_BUSY_TIMEOUT_SECONDS if busy_timeout is None else busy_timeout)
    key = (str(path), mode, timeout)
    with _ENGINES_LOCK:
        engine = _ENGINES.get(key)
        if engine is None:
            engine = _build_engine(path, mode, timeout)
            _ENGINES[key] = engine
        return engine


def _build_engine(path: Path, mode: str, timeout: float):
    engine = create_engine(
        _engine_url(path, mode),
        poolclass=NullPool,
        isolation_level="AUTOCOMMIT",
        connect_args={"timeout": timeout},
    )

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection, _record):  # pragma: no cover - exercised via repos
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute(f"PRAGMA busy_timeout={int(timeout * 1000)}")
            cursor.execute("PRAGMA foreign_keys=ON")
            if mode == "ro":
                cursor.execute("PRAGMA query_only=ON")
            else:
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=FULL")
        finally:
            cursor.close()

    return engine


def _is_busy(exc: OperationalError) -> bool:
    original = getattr(exc, "orig", None)
    code = getattr(original, "sqlite_errorcode", 0) & 0xFF
    return (
        code in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
        or "locked" in str(original or exc).lower()
    )


def busy_error() -> HTTPException:
    return HTTPException(503, "Registry busy; retry later", headers={"Retry-After": "1"})


def retry_locked(callable_, *, timeout=30.0, interval=0.05):
    """Bound retries for first-open journal conversion (can return SQLITE_BUSY at once)."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            return callable_()
        except (OperationalError, sqlite3.OperationalError) as exc:
            message = str(getattr(exc, "orig", exc)).lower()
            if "locked" not in message or time.monotonic() >= deadline:
                raise
            time.sleep(interval)


class DatabaseConnection:
    """Thin SQLAlchemy-backed connection adapter used by the repositories.

    Repositories keep their explicit SQL (``execute``/``executemany``) while every
    statement runs through SQLAlchemy. ``BEGIN IMMEDIATE`` starts an explicit
    transaction; ``commit``/``rollback`` and the context-manager exit honour it.
    """

    def __init__(self, connection):
        self._connection = connection
        self._transaction = False

    @property
    def raw(self):
        return self._connection.connection.driver_connection

    def execute(self, statement, parameters=()):
        if isinstance(statement, str):
            beginning = statement.lstrip().upper().startswith("BEGIN")
            result = self._connection.exec_driver_sql(statement, parameters or ()).mappings()
            if beginning:
                self._transaction = True
            return result
        return self._connection.execute(statement, parameters if parameters else {})

    def executemany(self, statement, parameters):
        if isinstance(statement, str):
            rows = list(parameters)
            if not rows:
                return None
            return self._connection.exec_driver_sql(statement, rows).mappings()
        return self._connection.execute(statement, parameters)

    def executescript(self, script):
        return self.raw.executescript(script)

    def backup(self, target):
        """SQLite backup API against the underlying driver connection (WAL-safe)."""
        return self.raw.backup(target)

    def commit(self):
        if not self._transaction:
            return
        try:
            self._connection.exec_driver_sql("COMMIT")
        except OperationalError as exc:
            # SQLite ends the transaction on some errors; a missing transaction is not fatal.
            if "no transaction" not in str(exc).lower():
                raise
        finally:
            self._transaction = False

    def rollback(self):
        if not self._transaction:
            return
        try:
            self._connection.exec_driver_sql("ROLLBACK")
        except OperationalError:
            pass
        finally:
            self._transaction = False

    def close(self):
        self._connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False


@contextmanager
def connection(db_path, *, mode="rw", busy_timeout=None):
    """Yield a :class:`DatabaseConnection`.

    Like the original ``MetadataManager.connection()``, no transaction is committed
    implicitly: callers issue an explicit ``COMMIT`` (or use ``Store.db()`` /
    ``warehouse_repository.db()`` which commit on success). Exceptions roll back.
    """
    db = DatabaseConnection(engine_for(db_path, mode=mode, busy_timeout=busy_timeout).connect())
    try:
        yield db
    except OperationalError as exc:
        db.rollback()
        if _is_busy(exc):
            raise busy_error() from exc
        raise
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def transaction(db_path, *, mode="rw", busy_timeout=None, immediate=True):
    """Explicit writer transaction (``BEGIN IMMEDIATE`` by default)."""
    with connection(db_path, mode=mode, busy_timeout=busy_timeout) as db:
        db.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
        yield db


def backup_database(source, target):
    """Snapshot a live SQLite database through the SQLite backup API (WAL-safe)."""
    engine = engine_for(source, mode="ro", busy_timeout=30)
    raw = engine.raw_connection()
    try:
        with closing(sqlite3.connect(target)) as destination:
            raw.driver_connection.backup(destination)
            destination.execute("PRAGMA journal_mode=DELETE")
    finally:
        raw.close()
