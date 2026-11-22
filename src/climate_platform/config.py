"""Single source of truth for climate_platform configuration.

Distinct, non-interchangeable storage roots (Phase 1):

- PACKAGE_RESOURCES: read-only files shipped inside the ``climate_platform`` package
  (resources, and legacy source-tree fallback). Never written at runtime.
- LOCAL_DATA_DIR: legacy data lake root that owns ``bronze``/``silver`` on a local disk
  during Phase 1. Relative values resolve under ``BASE_DIR``; absolute values are used
  as-is. The registry and accounting live beside it (``METADATA_DIR``).
- SCRATCH_DIR: disposable working space for processing temp files.
- S3_*: object storage for the Bronze backend.

Data paths are anchored on ``BASE_DIR`` (an explicit deployment root), never on the
process working directory. ``BASE_DIR`` defaults to the checkout root so legacy data
and runs keep working, and to the current directory only for an installed package
with no deployment root. A missing S3 deployment never silently falls back to local.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, Literal, Set

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PACKAGE_ROOT = Path(__file__).resolve().parent
# Checkout layout is <root>/src/climate_platform/config.py; installed packages are not.
CHECKOUT_ROOT = PACKAGE_ROOT.parent.parent if PACKAGE_ROOT.parent.name == "src" else None

Environment = Literal["development", "testing", "staging", "production"]


class APIKeyRecord(BaseModel):
    key_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    secret_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    client_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    role: Literal["collector", "admin"]
    expires_at: datetime
    not_before: datetime | None = None
    enabled: bool = True
    sources: Set[str] = Field(default_factory=set)

    @model_validator(mode="after")
    def validate_record(self):
        if self.expires_at.tzinfo is None or (self.not_before and self.not_before.tzinfo is None):
            raise ValueError("Key validity dates must include timezone")
        if self.not_before and self.not_before >= self.expires_at:
            raise ValueError("Key validity interval is empty")
        if (self.role == "admin") != (self.client_id == "admin"):
            raise ValueError("admin identity is reserved for the admin role")
        return self


def _default_local_data_dir() -> str:
    return "data_lake"


def _default_metadata_dir() -> str:
    return "metadata"


def _default_scratch_dir() -> str:
    return "data_lake/temp"


def _default_checkout_base_dir() -> Path:
    return CHECKOUT_ROOT if CHECKOUT_ROOT else Path.cwd()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ENVIRONMENT: Environment = "development"

    # Server Network Settings
    SERVER_HOST: str = "127.0.0.1"
    SERVER_PORT: int = 8000
    DEBUG: bool = False

    # Storage Roots (see module docstring). BASE_DIR is retained as the local deployment
    # anchor for legacy relative directories and the local Bronze/metadata paths.
    BASE_DIR: Path | None = None
    LOCAL_DATA_DIR: str = Field(default_factory=_default_local_data_dir)
    DATA_LAKE_DIR: str = "data_lake"
    METADATA_DIR: str = Field(default_factory=_default_metadata_dir)
    SCRATCH_DIR: str = Field(default_factory=_default_scratch_dir)
    TEMP_DIR: str | None = None  # legacy alias read into SCRATCH_DIR when SCRATCH_DIR unset
    STORAGE_BACKEND: Literal["local", "s3"] = "s3"
    S3_ENDPOINT: str = "http://minio:9000"
    S3_REGION: str = "us-east-1"
    S3_BUCKET_BRONZE: str = "climate-bronze"
    S3_BUCKET_SILVER: str = "climate-silver"
    S3_BUCKET_GOLD: str = "climate-gold"
    S3_BUCKET_WAREHOUSE: str = "climate-warehouse"
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""

    SQLITE_BUSY_TIMEOUT_SECONDS: float = Field(0.5, gt=0, le=5)

    READINESS_CACHE_SECONDS: float = Field(3, ge=0, le=10)
    READINESS_TIMEOUT_SECONDS: float = Field(0.5, gt=0, le=2)
    API_KEYS: list[APIKeyRecord] = Field(default_factory=list)
    ENABLE_STATIC_KEYS: bool = True  # migration compatibility; disable for Internet deployment
    RATE_LIMIT_PER_MINUTE: int = Field(120, gt=0)
    DAILY_UPLOAD_QUOTA_BYTES: int = Field(1024 * 1024 * 1024, gt=0)
    REQUIRE_SSE_KMS: bool = False
    REQUIRE_OBJECT_LOCK: bool = False

    # Ingestion Constraints
    MAX_FILE_SIZE_BYTES: int = 20 * 1024 * 1024  # 20 MB limit
    CHUNK_SIZE_BYTES: int = 1024 * 1024  # 1 MB stream chunk

    # Valid Climate Ingestion Sources
    ALLOWED_SOURCES: Set[str] = {"usdm", "noaa", "usgs", "nldas"}

    # Client API Key Credentials
    COLLECTOR_API_KEY: str = ""
    COLLECTOR_SOURCES: Set[str] = {"usdm", "noaa", "usgs", "nldas"}
    ENABLE_LEGACY_KEYS: bool = False
    CLIENT01_API_KEY: str = ""
    CLIENT02_API_KEY: str = ""
    ADMIN_API_KEY: str = ""

    @field_validator("BASE_DIR", mode="before")
    @classmethod
    def _empty_base_dir(cls, value):
        return None if value in ("", None) else value

    @model_validator(mode="after")
    def _resolve_roots(self):
        # TEMP_DIR is a legacy alias; SCRATCH_DIR is the canonical setting.
        if self.TEMP_DIR and "SCRATCH_DIR" not in self.model_fields_set:
            self.SCRATCH_DIR = self.TEMP_DIR
        if "LOCAL_DATA_DIR" not in self.model_fields_set:
            self.LOCAL_DATA_DIR = self.DATA_LAKE_DIR
        if self.BASE_DIR is None:
            self.BASE_DIR = _default_checkout_base_dir()
        return self

    @model_validator(mode="after")
    def validate_keys(self):
        if self.ENABLE_STATIC_KEYS and (
            not self.COLLECTOR_API_KEY.strip() or not self.ADMIN_API_KEY.strip()
        ):
            raise ValueError("COLLECTOR_API_KEY and ADMIN_API_KEY are required")
        if not self.ENABLE_STATIC_KEYS and not self.API_KEYS:
            raise ValueError("API_KEYS is required when static keys are disabled")
        if len({key.key_id for key in self.API_KEYS}) != len(self.API_KEYS):
            raise ValueError("Duplicate key_id")
        for key in self.API_KEYS:
            if not key.sources <= self.ALLOWED_SOURCES:
                raise ValueError("Unsupported key sources")
            if key.role == "collector" and not key.sources:
                raise ValueError("Collector keys require sources")
        identities = {}
        for key in self.API_KEYS:
            grant = (key.role, frozenset(key.sources))
            if key.client_id in identities and identities[key.client_id] != grant:
                raise ValueError("Rotating keys must preserve identity permissions")
            identities[key.client_id] = grant
        if self.ENABLE_STATIC_KEYS:
            static_grants = {
                "collector01": ("collector", frozenset(self.COLLECTOR_SOURCES)),
                "admin": ("admin", frozenset()),
            }
            if self.ENABLE_LEGACY_KEYS:
                static_grants.update(
                    client01=("collector", frozenset({"usdm", "noaa"})),
                    client02=("collector", frozenset({"usgs", "nldas"})),
                )
            for client, grant in identities.items():
                if client in static_grants and grant != static_grants[client]:
                    raise ValueError("Static and rotating keys must preserve identity permissions")
        if not self.COLLECTOR_SOURCES or not self.COLLECTOR_SOURCES <= self.ALLOWED_SOURCES:
            raise ValueError("COLLECTOR_SOURCES must contain supported sources")
        keys = [self.COLLECTOR_API_KEY, self.ADMIN_API_KEY]
        if self.ENABLE_LEGACY_KEYS:
            keys += [self.CLIENT01_API_KEY, self.CLIENT02_API_KEY]
        active = [key for key in keys if key]
        if len(active) != len(set(active)):
            raise ValueError("Configured API keys must be distinct")
        if any(key.startswith("REPLACE_WITH") for key in active):
            raise ValueError("Replace placeholder API keys before starting Server")
        if self.STORAGE_BACKEND == "s3" and (not self.S3_ACCESS_KEY or not self.S3_SECRET_KEY):
            raise ValueError("S3_ACCESS_KEY and S3_SECRET_KEY are required for S3 storage")
        return self

    @property
    def package_resources(self) -> Path:
        """Read-only resources shipped inside the package."""
        return PACKAGE_ROOT / "datasets" / "usdm" / "resources"

    @property
    def local_data_dir(self) -> Path:
        path = Path(self.LOCAL_DATA_DIR)
        return path if path.is_absolute() else self.BASE_DIR / path

    @property
    def bronze_path(self) -> Path:
        return self.local_data_dir / "bronze"

    @property
    def silver_path(self) -> Path:
        return self.local_data_dir / "silver"

    @property
    def warehouse_path(self) -> Path:
        return self.BASE_DIR / "warehouse"

    @property
    def metadata_path(self) -> Path:
        path = Path(self.METADATA_DIR)
        return path if path.is_absolute() else self.BASE_DIR / path

    @property
    def scratch_path(self) -> Path:
        path = Path(self.SCRATCH_DIR)
        return path if path.is_absolute() else self.BASE_DIR / path

    @property
    def temp_path(self) -> Path:
        """Legacy alias for scratch_path (interrupted-upload cleanup)."""
        return self.scratch_path

    @property
    def api_keys(self) -> Dict[str, str]:
        """Maps raw secret API key string to canonical client_id."""
        mapping: Dict[str, str] = {}
        if self.COLLECTOR_API_KEY:
            mapping[self.COLLECTOR_API_KEY] = "collector01"
        if self.ENABLE_LEGACY_KEYS and self.CLIENT01_API_KEY:
            mapping[self.CLIENT01_API_KEY] = "client01"
        if self.ENABLE_LEGACY_KEYS and self.CLIENT02_API_KEY:
            mapping[self.CLIENT02_API_KEY] = "client02"
        if self.ADMIN_API_KEY:
            mapping[self.ADMIN_API_KEY] = "admin"
        return mapping

    def ensure_directories(self) -> None:
        """Ensure all required data lake and metadata directories exist."""
        self.scratch_path.mkdir(parents=True, exist_ok=True)
        self.metadata_path.mkdir(parents=True, exist_ok=True)
        self.silver_path.mkdir(parents=True, exist_ok=True)
        self.warehouse_path.mkdir(parents=True, exist_ok=True)
        for source in self.ALLOWED_SOURCES:
            (self.bronze_path / source).mkdir(parents=True, exist_ok=True)


settings = Settings()
