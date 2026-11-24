"""Declarative bases, one ``MetaData`` per physical SQLite database.

Each database file keeps an independent ``MetaData`` so ``create_all`` never emits
tables that belong to another file. Constraint and index names mirror the original
hand-written DDL wherever they were explicit (``one_current_revision``,
``observation_owner``); the rest stays equivalent.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class RegistryBase(DeclarativeBase):
    """``metadata/ingestion.sqlite3`` — catalog registry."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class ControlBase(DeclarativeBase):
    """``control.sqlite3`` — Portal users, sessions, grants and control state."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class WarehouseBase(DeclarativeBase):
    """``warehouse.sqlite3`` — USDM builds, attempts and gold cells."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class AccessBase(DeclarativeBase):
    """``metadata/access.sqlite3`` — rate-limit and quota accounting."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
