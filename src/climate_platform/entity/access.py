"""ORM entity for the access accounting database (``metadata/access.sqlite3``)."""

from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from climate_platform.entity.base import AccessBase


class AccessUsage(AccessBase):
    __tablename__ = "usage"

    key_id: Mapped[str] = mapped_column(Text, primary_key=True)
    minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requests: Mapped[int | None] = mapped_column(Integer, nullable=True)
    day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
