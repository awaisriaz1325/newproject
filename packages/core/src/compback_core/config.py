"""Typed application configuration (12-factor, env-driven).

All settings are read from environment variables prefixed ``COMPBACK_``.
Secrets use ``SecretStr`` so they never appear in reprs or logs.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEV = "dev"
    TEST = "test"
    STAGING = "staging"
    PROD = "prod"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="COMPBACK_", env_file=".env", extra="ignore")

    env: Environment = Environment.DEV
    service_name: str = "compback"
    log_level: str = "INFO"
    log_json: bool = True

    # Application role (no BYPASSRLS, not table owner) and migration/owner role.
    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://compback_app:compback_app@localhost:5432/compback"
    )
    database_owner_url: SecretStr = SecretStr(
        "postgresql+psycopg://compback_owner:compback_owner@localhost:5432/compback"
    )
    db_pool_size: int = 5

    # Object storage (S3-compatible). "local" stores files on disk (dev/test only).
    storage_backend: str = "local"
    storage_local_root: str = "./.data/objects"
    storage_bucket: str = "compback-documents"
    storage_endpoint_url: str | None = None
    storage_region: str = "auto"
    signed_url_ttl_seconds: int = Field(default=120, ge=10, le=900)

    # Envelope encryption: master key provider. "local" uses a base64 32-byte key (dev/test).
    kms_backend: str = "local"
    local_master_key_b64: SecretStr | None = None
    kms_key_id: str | None = None

    # Sessions / auth
    session_idle_minutes: int = 60
    session_absolute_hours: int = 12
    cookie_secure: bool = True
    rate_limits_enabled: bool = True
    allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # Uploads
    max_upload_bytes: int = 50 * 1024 * 1024
    max_pdf_pages: int = 300
    clamav_host: str | None = None
    clamav_port: int = 3310

    # LLM
    llm_provider: str = "fake"
    llm_model: str = "claude-opus-5-5"
    anthropic_api_key: SecretStr | None = None
    llm_cost_cap_usd_per_analysis: Decimal = Decimal("5.00")

    @model_validator(mode="after")
    def _prod_safety(self) -> Settings:
        if self.env in (Environment.PROD, Environment.STAGING):
            if self.storage_backend == "local":
                raise ValueError("local storage backend is not allowed in staging/prod")
            if self.kms_backend == "local":
                raise ValueError("local KMS backend is not allowed in staging/prod")
            if self.llm_provider == "fake":
                raise ValueError("fake LLM provider is not allowed in staging/prod")
            if not self.cookie_secure:
                raise ValueError("cookie_secure must be true in staging/prod")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
