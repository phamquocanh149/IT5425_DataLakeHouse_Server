"""Catalog module wiring: one service over the SQLite registry + object storage."""

from climate_platform.modules.catalog.service import CatalogService
from climate_platform.repositories.catalog_repository import metadata_manager
from climate_platform.s3.module import object_repository

catalog_service = CatalogService(metadata_manager, object_repository)
