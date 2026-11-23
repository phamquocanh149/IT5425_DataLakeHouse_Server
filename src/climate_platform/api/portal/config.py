from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from climate_platform.config import CHECKOUT_ROOT


def _checkout_path(*parts) -> Path:
    # Legacy checkout default kept only as a fallback; PORTAL_STORAGE_ROOT/FRONTEND_ROOT win.
    return CHECKOUT_ROOT.joinpath(*parts) if CHECKOUT_ROOT else Path(*parts)


class PortalConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PORTAL_", extra="ignore")
    enabled: bool = False
    storage_root: Path = Field(default_factory=lambda: _checkout_path("data_lake", "portal"))
    frontend_root: Path = Field(
        default_factory=lambda: _checkout_path("..", "frontend-climate-platform", "dist")
    )
    origin: str = "https://localhost:8010"
    oidc_issuer: str = ""
    oidc_client_id: str = "climate-portal"
    oidc_client_secret: str = ""
    bootstrap_subject: str = ""
    demo: bool = False
    session_idle_seconds: int = 1800
    session_max_seconds: int = 28800
    selection_seconds: int = 900

    @model_validator(mode="after")
    def validate_paths(self):
        self.storage_root = self.storage_root.resolve()
        if any(p in {".test-runs", ".smoke", "data_crawl_USDM"} for p in self.storage_root.parts):
            raise ValueError("Portal storage must be independent of source/test storage")
        if self.enabled:
            for url in (self.origin, self.oidc_issuer):
                parsed = urlparse(url)
                if (
                    not parsed.hostname
                    or parsed.username
                    or parsed.password
                    or parsed.query
                    or parsed.fragment
                ):
                    raise ValueError("Invalid Portal URL")
                if parsed.scheme != "https":
                    if not (
                        self.demo
                        and parsed.scheme == "http"
                        and parsed.hostname in {"127.0.0.1", "localhost"}
                    ):
                        raise ValueError("Portal requires HTTPS outside explicit loopback demo")
            if urlparse(self.origin).path not in {"", "/"}:
                raise ValueError("Origin must not contain a path")
        return self

    @property
    def secure_cookie(self):
        return self.origin.startswith("https://")

    @property
    def callback(self):
        return self.origin.rstrip("/") + "/api/portal/v1/auth/callback"
