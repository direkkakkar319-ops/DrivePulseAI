"""Real PostgreSQL migrations, authenticated profile isolation, and concurrent upserts."""

import os
import subprocess
import sys
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.api import deps
from app.config import Settings
from app.main import create_app

pytestmark = pytest.mark.postgres
BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def database_url() -> str:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a dedicated PostgreSQL test database")
    if not (make_url(url).database or "").endswith("_test"):
        pytest.fail("TEST_DATABASE_URL database name must end in _test")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(BACKEND / "alembic.ini"),
            "upgrade",
            "head",
        ],
        env={**os.environ, "DATABASE_URL": url},
        check=True,
        cwd=BACKEND,
    )
    return url


@pytest.fixture
def client(database_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE users"))
    engine.dispose()

    # Only remote token verification is mocked; HTTP identity checks and real
    # PostgreSQL migrations, queries, and transactions run here.
    def claims(token: str, project_id: str) -> dict[str, object]:
        assert project_id == "drivepulse-d2034"
        return {
            "uid": token,
            "email": f"{token}@example.com",
            "name": f"Driver {token}",
            "email_verified": True,
        }

    monkeypatch.setattr(deps, "verify_token", claims)
    with TestClient(
        create_app(Settings(_env_file=None, database_url=database_url, cors_origins=[]))
    ) as value:
        yield value


def test_sync_is_idempotent_and_does_not_trust_body(client: TestClient) -> None:
    headers = {"Authorization": "Bearer alice"}
    first = client.put(
        "/api/v1/users/me",
        headers=headers,
        json={
            "firebase_uid": "victim",
            "email": "forged@example.com",
            "username": "forged",
        },
    )
    second = client.put("/api/v1/users/me", headers=headers)
    assert first.status_code == second.status_code == 200
    assert first.json()["firebase_uid"] == "alice"
    assert first.json()["email"] == "alice@example.com"
    assert first.json()["username"] == "Driver alice"
    assert first.json()["created_at"] == second.json()["created_at"]
    assert set(first.json()) == {
        "firebase_uid",
        "email",
        "username",
        "created_at",
        "updated_at",
    }
    assert first.headers["cache-control"] == "no-store"
    assert client.get("/api/v1/users/me", headers=headers).json() == second.json()


def test_users_cannot_read_each_others_profiles(client: TestClient) -> None:
    client.put("/api/v1/users/me", headers={"Authorization": "Bearer alice"})
    assert (
        client.get(
            "/api/v1/users/me", headers={"Authorization": "Bearer bob"}
        ).status_code
        == 404
    )
    bob = client.put("/api/v1/users/me", headers={"Authorization": "Bearer bob"})
    assert bob.json()["firebase_uid"] == "bob"
    assert (
        client.get(
            "/api/v1/users/alice", headers={"Authorization": "Bearer bob"}
        ).status_code
        == 404
    )


def test_concurrent_first_sync_creates_one_row(
    client: TestClient, database_url: str
) -> None:
    def sync(_: int) -> int:
        return client.put(
            "/api/v1/users/me", headers={"Authorization": "Bearer concurrent"}
        ).status_code

    with ThreadPoolExecutor(max_workers=6) as pool:
        assert list(pool.map(sync, range(12))) == [200] * 12
    engine = create_engine(database_url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM users")) == 1
    engine.dispose()


def test_profile_changes_keep_uid_and_creation_date(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = {"Authorization": "Bearer alice"}
    first = client.put("/api/v1/users/me", headers=headers).json()
    monkeypatch.setattr(
        deps,
        "verify_token",
        lambda *_: {"uid": "alice", "email": "new@example.com", "email_verified": True},
    )
    updated = client.put("/api/v1/users/me", headers=headers).json()
    assert updated["created_at"] == first["created_at"]
    assert updated["email"] == "new@example.com"
    assert updated["username"] is None


def test_schema_contains_no_authentication_secrets(database_url: str) -> None:
    engine = create_engine(database_url)
    assert {col["name"] for col in inspect(engine).get_columns("users")} == {
        "firebase_uid",
        "email",
        "username",
        "created_at",
        "updated_at",
    }
    engine.dispose()
