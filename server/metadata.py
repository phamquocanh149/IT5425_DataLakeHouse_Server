import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field

from server.config import settings

logger = logging.getLogger("climate_server.metadata")


class FileMetadata(BaseModel):
    file_id: str = Field(..., description="Unique UUID for this uploaded file")
    source: str = Field(..., description="Climate data source (usdm, noaa, usgs, nldas)")
    source_date: str = Field(..., description="Observation or publication date (YYYY-MM-DD)")
    client_id: str = Field(..., description="Authenticated client identifier")
    original_filename: str = Field(..., description="Sanitized original filename")
    stored_path: str = Field(..., description="Relative storage path in data lake")
    size_bytes: int = Field(..., ge=0, description="File size in bytes")
    sha256: str = Field(..., min_length=64, max_length=64, description="Calculated SHA-256 checksum")
    received_at: str = Field(..., description="UTC ISO-8601 timestamp when received")
    status: str = Field("VERIFIED", description="Verification status (VERIFIED, DUPLICATE, etc.)")


class MetadataManager:
    """Handles safe, atomic persistence and querying of ingestion metadata."""

    def __init__(self, metadata_dir: Optional[Path] = None):
        self.metadata_dir = metadata_dir or settings.metadata_path
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    def _get_filepath(self, file_id: str) -> Path:
        return self.metadata_dir / f"{file_id}.json"

    def save_metadata(self, metadata: FileMetadata) -> Path:
        """Atomically saves metadata to disk using a temporary file and rename.

        Ensures atomic commit so half-written or corrupted JSON files never occur.
        """
        target_path = self._get_filepath(metadata.file_id)
        temp_path = self.metadata_dir / f".{metadata.file_id}.tmp"

        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(metadata.model_dump(), f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())

            # Atomic replace on Windows & POSIX
            os.replace(temp_path, target_path)
            logger.info(
                "Metadata saved atomically for file_id=%s, source=%s, sha256=%s",
                metadata.file_id,
                metadata.source,
                metadata.sha256,
            )
            return target_path
        except Exception as e:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            logger.error("Failed to save metadata for file_id=%s: %s", metadata.file_id, str(e))
            raise

    def get_by_file_id(self, file_id: str) -> Optional[FileMetadata]:
        """Fetch metadata by file_id."""
        target_path = self._get_filepath(file_id)
        if not target_path.exists():
            return None
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return FileMetadata(**data)
        except Exception as e:
            logger.error("Error reading metadata file %s: %s", target_path, str(e))
            return None

    def find_by_sha256(self, sha256: str) -> Optional[FileMetadata]:
        """Search existing metadata for a matching SHA-256 checksum."""
        sha256_lower = sha256.lower()
        for json_file in self.metadata_dir.glob("*.json"):
            if json_file.name.startswith("."):
                continue
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("sha256", "").lower() == sha256_lower and data.get("status") == "VERIFIED":
                    return FileMetadata(**data)
            except Exception:
                continue
        return None

    def list_all(self, source_filter: Optional[str] = None) -> List[FileMetadata]:
        """List all verified metadata records, sorted newest first."""
        records: List[FileMetadata] = []
        for json_file in self.metadata_dir.glob("*.json"):
            if json_file.name.startswith("."):
                continue
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                record = FileMetadata(**data)
                if source_filter and record.source.lower() != source_filter.lower():
                    continue
                records.append(record)
            except Exception as e:
                logger.warning("Skipping invalid metadata file %s: %s", json_file, str(e))
                continue

        # Sort descending by received_at timestamp
        records.sort(key=lambda r: r.received_at, reverse=True)
        return records


metadata_manager = MetadataManager()
