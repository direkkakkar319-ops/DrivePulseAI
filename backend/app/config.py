"""Validated server-only Firebase and PostgreSQL configuration."""

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        extra="ignore",
        hide_input_in_errors=True,
    )
    database_url: SecretStr
    firebase_project_id: str = "drivepulse-d2034"
    cors_origins: list[str] = []
    ml_service_url: str | None = None
    ml_inference_api_key: SecretStr | None = None
    leaf_analysis_max_concurrent: int = Field(default=2, ge=1, le=4)
    leaf_ml_batch_size: int = Field(default=32, ge=1, le=256)
    leaf_upload_max_bytes: int = Field(
        default=2 * 1024 * 1024, ge=1024, le=8 * 1024 * 1024
    )
    leaf_upload_max_rows: int = Field(default=256, ge=1, le=10000)
    leaf_analysis_timeout_seconds: float = Field(
        default=120, gt=0, le=180, allow_inf_nan=False
    )
    kit_ml_batch_size: int = Field(default=32, ge=1, le=256)
    ml_request_timeout_seconds: float = Field(
        default=30, gt=0, le=120, allow_inf_nan=False
    )
    kit_upload_max_bytes: int = Field(
        default=2 * 1024 * 1024, ge=1024, le=16 * 1024 * 1024
    )
    kit_upload_max_rows: int = Field(default=50000, ge=2, le=200000)
    kit_upload_max_windows: int = Field(default=256, ge=2, le=1024)
    kit_upload_max_pairs: int = Field(default=256, ge=1, le=1024)
    kit_upload_max_segments: int = Field(default=16, ge=1, le=64)
    kit_upload_max_concurrent: int = Field(default=2, ge=1, le=4)
    kit_upload_max_batches: int = Field(default=8, ge=1, le=32)
    kit_upload_analysis_timeout_seconds: float = Field(
        default=60, gt=0, le=180, allow_inf_nan=False
    )

    @field_validator(
        "leaf_analysis_max_concurrent",
        "leaf_ml_batch_size",
        "leaf_upload_max_bytes",
        "leaf_upload_max_rows",
        "kit_ml_batch_size",
        "kit_upload_max_bytes",
        "kit_upload_max_rows",
        "kit_upload_max_windows",
        "kit_upload_max_pairs",
        "kit_upload_max_segments",
        "kit_upload_max_concurrent",
        "kit_upload_max_batches",
        mode="before",
    )
    @classmethod
    def batch_size_not_boolean(cls, value):
        if isinstance(value, bool):
            # Pydantic wraps ValueError; TypeError would escape validation.
            raise ValueError("KIT_ML_BATCH_SIZE must be an integer")  # noqa: TRY004
        return value

    @field_validator("ml_service_url")
    @classmethod
    def ml_https_only(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.strip().rstrip("/")
        try:
            url = urlsplit(value)
            valid = (
                url.scheme == "https"
                and bool(url.hostname)
                and url.username is None
                and url.password is None
                and not url.query
                and not url.fragment
                and "?" not in value
                and "#" not in value
                and not any(character.isspace() for character in value)
                and (url.port is None or 1 <= url.port <= 65535)
            )
        except ValueError:
            valid = False
        if not valid:
            raise ValueError(
                "ML_SERVICE_URL must be HTTPS without credentials or query"
            )
        return value

    @field_validator("database_url")
    @classmethod
    def postgres_only(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
            valid = url.drivername in {"postgresql", "postgresql+psycopg2"}
        except (ArgumentError, ValueError):
            valid = False
        if not valid:
            raise ValueError(
                "DATABASE_URL must use postgresql:// or postgresql+psycopg2://"
            )
        # SQLAlchemy 2.1 defaults plain PostgreSQL URLs to psycopg (v3).
        # Our declared driver is psycopg2; keep API and migrations consistent.
        # Replace only the scheme to preserve encoded credentials/query options.
        return SecretStr(
            value.get_secret_value().replace(
                "postgresql://", "postgresql+psycopg2://", 1
            )
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
