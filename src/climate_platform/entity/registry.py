"""ORM entities for the ingestion catalog (``metadata/ingestion.sqlite3``)."""

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from climate_platform.entity.base import RegistryBase


class ContentBlob(RegistryBase):
    __tablename__ = "content_blobs"

    sha256: Mapped[str] = mapped_column(Text, primary_key=True)
    stored_path: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (CheckConstraint("size_bytes>=0", name="content_blobs_size_non_negative"),)


class Observation(RegistryBase):
    __tablename__ = "observations"

    file_id: Mapped[str] = mapped_column(Text, primary_key=True)
    client_id: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_date: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_key: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    stored_path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(Text, ForeignKey("content_blobs.sha256"), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    received_at: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_file_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("observations.file_id"), nullable=True
    )
    is_current: Mapped[int] = mapped_column(Integer, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    s3_bucket: Mapped[str | None] = mapped_column(Text, nullable=True)
    s3_object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    s3_version_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("revision>=1", name="observations_revision_positive"),
        CheckConstraint("is_current IN (0,1)", name="observations_is_current_boolean"),
        UniqueConstraint(
            "source", "source_date", "dataset_key", "sha256", name="observations_identity_sha256"
        ),
        UniqueConstraint(
            "source",
            "source_date",
            "dataset_key",
            "revision",
            name="observations_identity_revision",
        ),
        Index(
            "one_current_revision",
            "source",
            "source_date",
            "dataset_key",
            unique=True,
            sqlite_where=text("is_current=1"),
        ),
        Index("observation_owner", "client_id", "source"),
    )


class RecoveryReport(RegistryBase):
    __tablename__ = "recovery_reports"

    report_id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    report_json: Mapped[str] = mapped_column(Text, nullable=False)
