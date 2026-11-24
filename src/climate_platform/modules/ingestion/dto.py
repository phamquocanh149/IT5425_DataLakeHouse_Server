"""Ingestion DTOs (request/response shapes)."""

from typing import Optional

from pydantic import BaseModel

from climate_platform.entity.view import FileMetadata


class IngestionResponse(BaseModel):
    status: str
    message: str
    metadata: Optional[FileMetadata] = None
