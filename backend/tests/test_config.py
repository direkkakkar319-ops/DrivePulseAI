"""Ensure PostgreSQL URLs select the installed driver across SQLAlchemy versions."""

import pytest

from app.config import Settings
from app.database import build_engine


@pytest.mark.parametrize("scheme", ["postgresql", "postgresql+psycopg2"])
def test_postgres_urls_use_psycopg2_without_changing_credentials(scheme: str) -> None:
    suffix = "user:p%40ss%2Fword@localhost:5432/test?sslmode=require"
    settings = Settings(_env_file=None, database_url=f"{scheme}://{suffix}")
    assert settings.database_url.get_secret_value() == f"postgresql+psycopg2://{suffix}"
    engine = build_engine(settings)
    try:
        assert engine.dialect.driver == "psycopg2"
        assert engine.url.password == "p@ss/word"
        assert engine.url.query["sslmode"] == "require"
    finally:
        engine.dispose()
