"""Environment settings for the API and authentication."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./drivepulse.db"
    session_hours: int = Field(default=24, ge=1, le=168)
    google_web_client_id: str = ""
    cors_origins: list[str] = ["http://localhost:8081"]


settings = Settings()
