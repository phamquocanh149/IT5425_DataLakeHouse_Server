"""ORM entities for the USDM warehouse (``warehouse.sqlite3``)."""

from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from climate_platform.entity.base import WarehouseBase

GOLD_WEEKLY_VIEW = """
CREATE VIEW IF NOT EXISTS gold_weekly AS
    SELECT build_id,time,drought,count(*) AS cell_count
    FROM gold_cells GROUP BY build_id,time,drought
"""


class Build(WarehouseBase):
    __tablename__ = "builds"

    build_id: Mapped[str] = mapped_column(Text, primary_key=True)
    file_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_date: Mapped[str] = mapped_column(Text, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    manifest: Mapped[str] = mapped_column(Text, nullable=False)
    completed_at: Mapped[str] = mapped_column(Text, nullable=False)


class Attempt(WarehouseBase):
    __tablename__ = "attempts"

    attempt_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_date: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class GoldCell(WarehouseBase):
    __tablename__ = "gold_cells"

    build_id: Mapped[str] = mapped_column(Text, ForeignKey("builds.build_id"), primary_key=True)
    time: Mapped[str] = mapped_column(Text, primary_key=True)
    grid: Mapped[str] = mapped_column(Text, primary_key=True)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    drought: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "drought IN ('0','D0','D1','D2','D3','D4')", name="gold_cells_drought_valid"
        ),
    )
