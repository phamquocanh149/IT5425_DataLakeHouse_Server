"""Composition root (AppModule): build the single FastAPI application.

Only wiring lives here: create the app, run the lifespan, include the module routers,
add middleware and register the shared exception filters. Feature behaviour stays in
``modules/*``.
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool

from climate_platform.common.errors import register_exception_handlers
from climate_platform.common.middleware import AccessMiddleware
from climate_platform.config import settings
from climate_platform.repositories.access_repository import initialize_access_store
from climate_platform.repositories.catalog_repository import metadata_manager
from climate_platform.modules.ingestion.module import build_ingestion_module
from climate_platform.modules.system.module import build_system_module
from climate_platform.modules.system.readiness import readiness, validate_storage

# Configure server logging
logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("climate_platform.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle event to initialize directories and check configuration."""
    logger.info("Initializing Climate Data Lake Server...")
    settings.ensure_directories()
    await run_in_threadpool(metadata_manager.initialize)
    await run_in_threadpool(initialize_access_store)
    await run_in_threadpool(validate_storage)
    readiness.reset()
    logger.info(
        "Storage ready. Bronze path: %s | Active clients: %s",
        settings.bronze_path,
        sorted(
            {key.client_id for key in settings.API_KEYS}
            | (set(settings.api_keys.values()) if settings.ENABLE_STATIC_KEYS else set())
        ),
    )
    yield
    logger.info("Shutting down Climate Data Lake Server...")


app = FastAPI(
    title="Climate Data Lake Ingestion Server",
    description="Distributed Climate Data Lake - Medallion Bronze Ingestion Layer",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(AccessMiddleware)
register_exception_handlers(app)

# Portal is opt-in; existing collectors and deployment defaults remain unchanged.
from climate_platform.modules.portal.config import PortalConfig  # noqa: E402

portal_config = PortalConfig()
if portal_config.enabled:
    from climate_platform.modules.portal.module import install_portal

    install_portal(app, portal_config)

app.include_router(build_system_module())
app.include_router(build_ingestion_module())

# CORS setup (allow local development if needed)
# No browser cross-origin access is needed by the HTTPX client.
