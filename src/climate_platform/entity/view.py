"""Pydantic entity views (registry row <-> transport shape).

Neutral home (no feature-module imports) so both the catalog repository and the ingestion
module can map rows to the same view without the data layer depending on a module.
"""

from typing import Optional

from pydantic import BaseModel, Field


class FileMetadata(BaseModel):
    file_id: str = Field(..., description="Unique UUID for this uploaded file")
    source: str = Field(..., description="Climate data source (usdm, noaa, usgs, nldas)")
    source_date: str = Field(..., description="Observation or publication date (YYYY-MM-DD)")
    client_id: str = Field(..., description="Authenticated client identifier")
    original_filename: str = Field(..., description="Sanitized original filename")
    stored_path: str = Field(..., description="Relative storage path in data lake")
    size_bytes: int = Field(..., ge=0, description="File size in bytes")
    sha256: str = Field(
        ..., min_length=64, max_length=64, description="Calculated SHA-256 checksum"
    )
    received_at: str = Field(..., description="UTC ISO-8601 timestamp when received")
    dataset_key: str = ""
    s3_bucket: Optional[str] = None
    s3_object_key: Optional[str] = None
    s3_version_id: Optional[str] = None
    revision: int = 1
    previous_file_id: Optional[str] = None
    is_current: bool = True
    error_message: Optional[str] = None
    status: str = Field("VERIFIED", description="Verification status (VERIFIED, DUPLICATE, etc.)")
