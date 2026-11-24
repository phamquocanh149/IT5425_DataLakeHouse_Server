"""ORM entities for the Portal control store (``control.sqlite3``)."""

from sqlalchemy import Float, ForeignKey, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from climate_platform.entity.base import ControlBase


class User(ControlBase):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    username: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)


class PortalSession(ControlBase):
    __tablename__ = "sessions"

    token: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.user_id"), nullable=False)
    csrf: Mapped[str] = mapped_column(Text, nullable=False)
    created: Mapped[float] = mapped_column(Float, nullable=False)
    last_used: Mapped[float] = mapped_column(Float, nullable=False)


class Grant(ControlBase):
    __tablename__ = "grants"

    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.user_id"), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(Text, primary_key=True)
    layer: Mapped[str] = mapped_column(Text, primary_key=True)
    actions: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class Transient(ControlBase):
    __tablename__ = "transient"

    token: Mapped[str] = mapped_column(Text, primary_key=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[str] = mapped_column(Text, nullable=False)
    expires: Mapped[float] = mapped_column(Float, nullable=False)


class Audit(ControlBase):
    __tablename__ = "audit"

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    actor: Mapped[str | None] = mapped_column(Text, nullable=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    target: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str] = mapped_column(Text, nullable=False)
    request_id: Mapped[str | None] = mapped_column(Text, nullable=True)


class Config(ControlBase):
    __tablename__ = "config"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class PortalUsage(ControlBase):
    __tablename__ = "usage"

    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    category: Mapped[str] = mapped_column(Text, primary_key=True)
    minute: Mapped[int] = mapped_column(Integer, nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False)


class Lease(ControlBase):
    __tablename__ = "leases"

    lease_id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    expires: Mapped[float] = mapped_column(Float, nullable=False)
