"""Storage wiring: select the object repository for the configured backend."""

from climate_platform.config import settings


def object_repository():
    """Return the object repository for ``STORAGE_BACKEND`` (resolved at call time)."""
    if settings.STORAGE_BACKEND == "s3":
        from climate_platform.s3.minio_repository import S3Storage

        return S3Storage()
    from climate_platform.s3.local_repository import LocalObjectRepository

    return LocalObjectRepository()
