"""Database readiness runs only SELECT 1 and never discloses internal errors."""

import os
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app import main
from app.config import Settings


@pytest.fixture
def engine(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    value = MagicMock()
    connection = value.connect.return_value.__enter__.return_value
    connection.execute.return_value.scalar_one.return_value = 1
    monkeypatch.setattr(main, "build_engine", lambda _: value)
    return value


def application():
    return main.create_app(
        Settings(_env_file=None, database_url="postgresql://test:test@localhost/unused")
    )


def test_database_readiness_executes_only_select_and_releases_connection(engine):
    with TestClient(application()) as client:
        response = client.get("/health/db")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}
    engine.connect.assert_called_once_with()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.assert_called_once()
    assert str(connection.execute.call_args.args[0]) == "SELECT 1"
    assert connection.execute.call_args.kwargs == {}
    connection.execute.return_value.scalar_one.assert_called_once_with()
    connection.commit.assert_not_called()
    engine.begin.assert_not_called()
    engine.connect.return_value.__exit__.assert_called_once()
    engine.dispose.assert_called_once_with()


@pytest.mark.parametrize("stage", ["connect", "execute", "fetch"])
def test_database_failure_is_generic_503(engine, stage):
    error = OperationalError(
        "private SQL", {}, Exception("postgresql://private:secret@internal/database")
    )
    connection = engine.connect.return_value.__enter__.return_value
    if stage == "connect":
        engine.connect.side_effect = error
    elif stage == "execute":
        connection.execute.side_effect = error
    else:
        connection.execute.return_value.scalar_one.side_effect = error
    with TestClient(application()) as client:
        response = client.get("/health/db")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
    assert "secret" not in response.text
    assert "private" not in response.text
    assert "internal" not in response.text
    if stage != "connect":
        engine.connect.return_value.__exit__.assert_called_once()


def test_liveness_remains_independent_of_database(engine):
    engine.connect.side_effect = OperationalError("", {}, Exception("unavailable"))
    with TestClient(application()) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    engine.connect.assert_not_called()


@pytest.mark.postgres
def test_readiness_against_postgres_without_schema_or_record_changes():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL for the read-only PostgreSQL readiness test")
    with TestClient(
        main.create_app(Settings(_env_file=None, database_url=url))
    ) as client:
        response = client.get("/health/db")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}
