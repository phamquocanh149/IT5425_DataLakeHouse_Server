"""Ingestion routes: accept collector uploads and list ingested metadata."""

from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from climate_platform.entity.view import FileMetadata
from climate_platform.modules.authorization.services.policy import allowed_sources
from climate_platform.modules.ingestion.dto import IngestionResponse
from climate_platform.modules.ingestion.errors import IngestionError


def ingestion_router(service, get_current_client, authorize_upload) -> APIRouter:
    router = APIRouter()

    @router.post(
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
        authorize_upload(client_id, source)
        try:
            return await service.process_file_upload(
                upload_file=file,
                source=source,
                source_date=source_date,
                client_id=client_id,
                dataset_key=dataset_key,
            )
        except IngestionError as exc:
            raise HTTPException(exc.status, exc.detail) from None

    @router.get(
        "/uploads",
        tags=["Ingestion"],
        summary="List ingested files and their metadata",
        response_model=List[FileMetadata],
    )
    async def list_uploads(
        source: Optional[str] = Query(
            None, description="Optional filter by source (usdm, noaa, usgs, nldas)"
        ),
        client_id: str = Depends(get_current_client),
    ):
        """Returns the list of all verified ingested files with metadata. Requires client authentication."""
        if client_id != "admin" and source and source not in allowed_sources(client_id):
            raise HTTPException(403, "Source is not authorized")
        return await service.list_uploads(client_id, source)

    return router
