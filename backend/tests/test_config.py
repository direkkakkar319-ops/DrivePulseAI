"""Ensure PostgreSQL URLs select the installed driver across SQLAlchemy versions."""

import pytest

from app.config import Settings
from app.database import build_engine


@pytest.mark.parametrize("size", [0, -1, 257, True, 1.5, "invalid"])
def test_ml_batch_size_rejects_invalid_configuration(size):
    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            database_url="postgresql://test:test@localhost/unused",
            kit_ml_batch_size=size,
        )


@pytest.mark.parametrize("seconds", [0, -1, 121, float("nan"), float("inf")])
def test_ml_timeout_rejects_invalid_configuration(seconds):
    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            database_url="postgresql://test:test@localhost/unused",
            ml_request_timeout_seconds=seconds,
        )


@pytest.mark.parametrize(
    "url",
    [
        "http://ml.example",
        "https://user:private@ml.example",
        "https://ml.example/?",
        "https://ml.example/#",
        "https://ml.example/?key=private",
        "invalid",
        "https://ml.example:invalid",
    ],
)
def test_ml_url_rejects_credentials_queries_and_non_https(url):
    with pytest.raises(ValueError) as error:
        Settings(
            _env_file=None,
            database_url="postgresql://test:test@localhost/unused",
            ml_service_url=url,
        )
    assert "private" not in str(error.value)


def test_ml_environment_and_secret_masking(monkeypatch):
    import secrets

    key = secrets.token_urlsafe(32)
    monkeypatch.setenv("ML_SERVICE_URL", "https://ml.example/prefix/")
    monkeypatch.setenv("ML_INFERENCE_API_KEY", key)
    monkeypatch.setenv("KIT_ML_BATCH_SIZE", "16")
    monkeypatch.setenv("ML_REQUEST_TIMEOUT_SECONDS", "20")
    settings = Settings(
        _env_file=None, database_url="postgresql://test:test@localhost/unused"
    )
    assert settings.ml_service_url == "https://ml.example/prefix"
    assert settings.kit_ml_batch_size == 16
    assert settings.ml_request_timeout_seconds == 20
    assert settings.ml_inference_api_key.get_secret_value() == key
    assert key not in repr(settings)


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
