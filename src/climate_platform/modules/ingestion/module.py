"""Ingestion module wiring: controller + service + authentication/authorization guards."""

from fastapi import APIRouter

from climate_platform.modules.auth.guards import get_current_client
from climate_platform.modules.authorization.guards.require_source import authorize_upload
from climate_platform.modules.catalog.module import catalog_service
from climate_platform.modules.ingestion.controller import ingestion_router
from climate_platform.modules.ingestion.service import IngestionService


def build_ingestion_module() -> APIRouter:
    service = IngestionService(catalog_service)
    return ingestion_router(service, get_current_client, authorize_upload)
