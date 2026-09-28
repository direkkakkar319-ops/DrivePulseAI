"""Validated server-only Firebase and PostgreSQL configuration."""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env", extra="ignore"
    )
    database_url: SecretStr
    firebase_project_id: str = "drivepulse-d2034"
    cors_origins: list[str] = []

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
