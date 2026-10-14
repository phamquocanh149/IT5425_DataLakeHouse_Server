from pathlib import Path
from typing import Dict, Set
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Server Network Settings
    SERVER_HOST: str = "127.0.0.1"
    SERVER_PORT: int = 8000
    DEBUG: bool = False

    # Base Directories
    BASE_DIR: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    DATA_LAKE_DIR: str = "data_lake"
    METADATA_DIR: str = "metadata"
    TEMP_DIR: str = "data_lake/temp"

    # Ingestion Constraints
    MAX_FILE_SIZE_BYTES: int = 20 * 1024 * 1024  # 20 MB limit
    CHUNK_SIZE_BYTES: int = 1024 * 1024          # 1 MB stream chunk

    # Valid Climate Ingestion Sources
    ALLOWED_SOURCES: Set[str] = {"usdm", "noaa", "usgs", "nldas"}

    # Client API Key Credentials
    CLIENT01_API_KEY: str = ""
    CLIENT02_API_KEY: str = ""
    ADMIN_API_KEY: str = ""

    @property
    def bronze_path(self) -> Path:
        return self.BASE_DIR / self.DATA_LAKE_DIR / "bronze"

    @property
    def silver_path(self) -> Path:
        return self.BASE_DIR / self.DATA_LAKE_DIR / "silver"

    @property
    def warehouse_path(self) -> Path:
        return self.BASE_DIR / "warehouse"

    @property
    def metadata_path(self) -> Path:
        return self.BASE_DIR / self.METADATA_DIR

    @property
    def temp_path(self) -> Path:
        return self.BASE_DIR / self.TEMP_DIR

    @property
    def api_keys(self) -> Dict[str, str]:
        """Maps raw secret API key string to canonical client_id."""
        mapping: Dict[str, str] = {}
        if self.CLIENT01_API_KEY:
            mapping[self.CLIENT01_API_KEY] = "client01"
        if self.CLIENT02_API_KEY:
            mapping[self.CLIENT02_API_KEY] = "client02"
        if self.ADMIN_API_KEY:
            mapping[self.ADMIN_API_KEY] = "admin"
        return mapping

    def ensure_directories(self) -> None:
        """Ensure all required data lake and metadata directories exist."""
        self.temp_path.mkdir(parents=True, exist_ok=True)
        self.metadata_path.mkdir(parents=True, exist_ok=True)
        self.silver_path.mkdir(parents=True, exist_ok=True)
        self.warehouse_path.mkdir(parents=True, exist_ok=True)
        for source in self.ALLOWED_SOURCES:
            (self.bronze_path / source).mkdir(parents=True, exist_ok=True)


settings = Settings()
