import logging
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import Depends, FastAPI, File, Form, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from server.config import settings
from server.ingestion import IngestionResponse, process_file_upload
from server.metadata import FileMetadata, metadata_manager
from server.security import get_current_client, authorize_upload, allowed_sources

# Configure server logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("climate_server.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle event to initialize directories and check configuration."""
    logger.info("Initializing Climate Data Lake Server...")
    settings.ensure_directories()
    with metadata_manager.connection():
        pass
    logger.info(
        "Storage ready. Bronze path: %s | Active clients: %s",
        settings.bronze_path,
        list(set(settings.api_keys.values())),
    )
    yield
    logger.info("Shutting down Climate Data Lake Server...")


app = FastAPI(
    title="Climate Data Lake Ingestion Server",
    description="Distributed Climate Data Lake - Medallion Bronze Ingestion Layer",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS setup (allow local development if needed)
# No browser cross-origin access is needed by the HTTPX client.


@app.get(
    "/health",
    tags=["System"],
    summary="Health check endpoint",
    response_model=dict,
)
async def health_check():
    """Returns server health and service identifier."""
    return {
        "status": "ok",
        "service": "climate-data-server",
    }


@app.post(
    "/upload",
    tags=["Ingestion"],
    summary="Upload and ingest climate dataset into Bronze Lake",
    response_model=IngestionResponse,
    status_code=status.HTTP_200_OK,
)
async def upload_dataset(
    file: UploadFile = File(..., description="Raw climate data file"),
    source: str = Form(..., description="Data source: usdm, noaa, usgs, or nldas"),
    source_date: str = Form(..., description="Observation or publication date (YYYY-MM-DD)"),
    client_id: str = Depends(get_current_client),
    dataset_key: Optional[str] = Form(None),
):
    """Accepts multipart/form-data upload, verifies integrity, deduplicates by SHA-256,

    and stores the file atomically in the Bronze Data Lake.
    """
    logger.info(
        "Received upload request from client '%s': filename='%s', source='%s', source_date='%s'",
        client_id,
        file.filename,
        source,
        source_date,
    )
    authorize_upload(client_id, source)
    result = await process_file_upload(
        upload_file=file,
        source=source,
        source_date=source_date,
        client_id=client_id,
        dataset_key=dataset_key,
    )
    return result


@app.get(
    "/uploads",
    tags=["Ingestion"],
    summary="List ingested files and their metadata",
    response_model=List[FileMetadata],
)
async def list_uploads(
    source: Optional[str] = Query(None, description="Optional filter by source (usdm, noaa, usgs, nldas)"),
    client_id: str = Depends(get_current_client),
):
    """Returns the list of all verified ingested files with metadata. Requires client authentication."""
    logger.info("Client '%s' requested upload list (source_filter=%s)", client_id, source)
    if client_id != "admin" and source and source not in allowed_sources(client_id):
        from fastapi import HTTPException
        raise HTTPException(403, "Source is not authorized")
    return metadata_manager.list_all(source_filter=source,
        client_id=None if client_id == "admin" else client_id,
        sources=None if client_id == "admin" else allowed_sources(client_id))
