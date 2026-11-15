"""Real PostgreSQL Garage lifecycle, owner isolation, serialized writes and migrations."""

import os
import subprocess
import sys
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
import test_onboarding as onboarding_tests
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from test_onboarding import VEHICLE, first, headers
from test_user_profiles import BACKEND

from app.api import deps

pytestmark = pytest.mark.postgres


@pytest.fixture(scope="module")
def database_url() -> str:
    return onboarding_tests.database_url.__wrapped__()


@pytest.fixture
def client(database_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    yield from onboarding_tests.client.__wrapped__(database_url, monkeypatch)


def add(
    client: TestClient, name: str = "Second", request_id: str | None = None
) -> dict:
    response = client.post(
        "/api/v1/vehicles",
        headers={**headers(), **({"X-Vehicle-ID": request_id} if request_id else {})},
        json={**VEHICLE, "model": name},
    )
    assert response.status_code == 201
    return response.json()


def state(client: TestClient) -> dict:
    return client.get("/api/v1/onboarding", headers=headers()).json()


def test_edit_owned_metadata_preserves_identity_and_selection(
    client: TestClient,
) -> None:
    initial = first(client)
    vehicle_id = initial["active_vehicle_id"]
    changed = {
        **VEHICLE,
        "powertrain": "hybrid",
        "fuel_type": "diesel-electric",
        "nickname": "Family car",
        "year": 2025,
    }
    result = client.put(
        f"/api/v1/vehicles/{vehicle_id}", headers=headers(), json=changed
    )
    assert result.status_code == 200
    saved = result.json()
    assert saved["completed_at"] == initial["completed_at"]
    assert saved["active_vehicle_id"] == vehicle_id
    assert saved["vehicles"][0]["nickname"] == "Family car"
    assert saved["vehicles"][0]["created_at"] == initial["vehicles"][0]["created_at"]
    assert state(client) == saved


def test_delete_first_clears_reference_without_resetting_completion(
    client: TestClient,
) -> None:
    initial = first(client)
    second = add(client)
    client.put(f"/api/v1/vehicles/{second['id']}/active", headers=headers())
    result = client.delete(
        f"/api/v1/vehicles/{initial['first_vehicle_id']}", headers=headers()
    )
    assert result.status_code == 200
    saved = result.json()
    assert saved["first_vehicle_id"] is None
    assert saved["active_vehicle_id"] == second["id"]
    assert saved["completed_at"] == initial["completed_at"]
    assert (
        client.put(
            "/api/v1/onboarding/first-vehicle", headers=headers(), json=VEHICLE
        ).status_code
        == 409
    )


def test_active_deletion_uses_created_time_then_uuid(
    client: TestClient, database_url: str
) -> None:
    initial = first(client)
    third, second = add(client, "Third"), add(client, "Second")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE vehicles SET created_at = '2026-01-01T00:00:00Z' WHERE owner_uid = 'alice'"
            )
        )
    engine.dispose()
    response = client.delete(
        f"/api/v1/vehicles/{initial['active_vehicle_id']}", headers=headers()
    )
    assert response.status_code == 200
    assert response.json()["active_vehicle_id"] == min(
        third["id"], second["id"], key=UUID
    )


def test_last_deletion_and_readd_preserve_completed_onboarding(
    client: TestClient,
) -> None:
    initial = first(client)
    response = client.delete(
        f"/api/v1/vehicles/{initial['active_vehicle_id']}", headers=headers()
    )
    assert response.status_code == 200
    empty = state(client)
    assert empty["vehicles"] == []
    assert empty["active_vehicle_id"] is empty["first_vehicle_id"] is None
    assert empty["completed_at"] == initial["completed_at"]
    vehicle = add(client)
    assert state(client)["active_vehicle_id"] == vehicle["id"]
    assert state(client)["first_vehicle_id"] is None
    assert state(client)["completed_at"] == initial["completed_at"]
    another = add(client, "Another")
    assert another["id"] != state(client)["active_vehicle_id"]


def test_completed_empty_account_survives_a_new_server_instance(
    client: TestClient,
    database_url: str,
) -> None:
    from app.config import Settings
    from app.main import create_app

    initial = first(client)
    assert (
        client.delete(
            f"/api/v1/vehicles/{initial['active_vehicle_id']}", headers=headers()
        ).status_code
        == 200
    )
    # No provider memory, local storage, or server instance is shared with this app.
    with TestClient(
        create_app(Settings(_env_file=None, database_url=database_url))
    ) as restarted:
        restored = restarted.get("/api/v1/onboarding", headers=headers()).json()
        assert restored["firebase_uid"] == initial["firebase_uid"]
        assert restored["profile_completed_at"] == initial["profile_completed_at"]
        assert restored["completed_at"] == initial["completed_at"]
        assert restored["vehicles"] == []
        assert restored["active_vehicle_id"] is None


@pytest.mark.parametrize("method", ["put", "delete"])
def test_edit_delete_are_owner_scoped_and_protected(
    client: TestClient, method: str
) -> None:
    vehicle_id = first(client)["active_vehicle_id"]
    request = getattr(client, method)
    kwargs = {"json": VEHICLE} if method == "put" else {}
    assert request(f"/api/v1/vehicles/{vehicle_id}", **kwargs).status_code == 401
    assert (
        request(
            f"/api/v1/vehicles/{vehicle_id}", headers=headers("bob"), **kwargs
        ).status_code
        == 404
    )
    assert (
        request(
            f"/api/v1/vehicles/{vehicle_id}",
            headers={**headers("bob"), "X-Account-UID": "alice"},
            **kwargs,
        ).status_code
        == 409
    )
    assert state(client)["active_vehicle_id"] == vehicle_id


def test_edit_rejects_invalid_metadata_and_forged_owner(client: TestClient) -> None:
    vehicle_id = first(client)["active_vehicle_id"]
    for override in [
        {"owner_uid": "bob"},
        {"year": 1800},
        {"fuel_type": "petrol"},
        {"manufacturer": ""},
    ]:
        assert (
            client.put(
                f"/api/v1/vehicles/{vehicle_id}",
                headers=headers(),
                json={**VEHICLE, **override},
            ).status_code
            == 422
        )
    assert state(client)["vehicles"][0]["manufacturer"] == VEHICLE["manufacturer"]


def test_concurrent_creation_retries_do_not_duplicate_or_switch_active(
    client: TestClient,
) -> None:
    initial = first(client)
    request_id = str(uuid4())
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(
            pool.map(lambda _: add(client, request_id=request_id), range(12))
        )
    assert {item["id"] for item in results} == {request_id}
    assert len(state(client)["vehicles"]) == 2
    assert state(client)["active_vehicle_id"] == initial["active_vehicle_id"]
    assert (
        client.post(
            "/api/v1/vehicles",
            headers={**headers(), "X-Vehicle-ID": request_id},
            json=VEHICLE,
        ).status_code
        == 409
    )


def test_concurrent_delete_select_and_add_leave_valid_references(
    client: TestClient,
) -> None:
    first_id = first(client)["active_vehicle_id"]
    second = add(client)
    operations = [
        lambda: client.delete(f"/api/v1/vehicles/{first_id}", headers=headers()),
        lambda: client.delete(f"/api/v1/vehicles/{second['id']}", headers=headers()),
        lambda: client.put(f"/api/v1/vehicles/{first_id}/active", headers=headers()),
        lambda: client.post(
            "/api/v1/vehicles",
            headers=headers(),
            json={**VEHICLE, "model": "Concurrent"},
        ),
    ]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda operation: operation(), operations))
    assert all(result.status_code in (200, 201, 404) for result in results)
    saved = state(client)
    assert len(saved["vehicles"]) == 1
    assert saved["active_vehicle_id"] == saved["vehicles"][0]["id"]
    assert saved["first_vehicle_id"] is None and saved["completed_at"]


def test_failed_delete_rolls_back_references_and_can_retry(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial = first(client)

    def fail(*_: object) -> None:
        raise OperationalError("commit", {}, Exception("private"))

    with monkeypatch.context() as patch:
        patch.setattr(Session, "commit", fail)
        response = client.delete(
            f"/api/v1/vehicles/{initial['active_vehicle_id']}", headers=headers()
        )
        assert response.status_code == 503
    assert state(client) == initial
    assert (
        client.delete(
            f"/api/v1/vehicles/{initial['active_vehicle_id']}", headers=headers()
        ).status_code
        == 200
    )


def test_vehicle_mutations_require_verified_email(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    vehicle_id = first(client)["active_vehicle_id"]
    monkeypatch.setattr(
        deps,
        "verify_token",
        lambda *_: {
            "uid": "alice",
            "email": "alice@example.com",
            "email_verified": False,
        },
    )
    assert (
        client.put(
            f"/api/v1/vehicles/{vehicle_id}", headers=headers(), json=VEHICLE
        ).status_code
        == 403
    )
    assert (
        client.delete(f"/api/v1/vehicles/{vehicle_id}", headers=headers()).status_code
        == 403
    )


def test_concurrent_edit_and_delete_never_recreate_vehicle(client: TestClient) -> None:
    vehicle_id = first(client)["active_vehicle_id"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        delete = pool.submit(
            client.delete, f"/api/v1/vehicles/{vehicle_id}", headers=headers()
        )
        edit = pool.submit(
            client.put,
            f"/api/v1/vehicles/{vehicle_id}",
            headers=headers(),
            json={**VEHICLE, "nickname": "Concurrent edit"},
        )
        assert delete.result().status_code == 200
        assert edit.result().status_code in (200, 404)
    assert state(client)["vehicles"] == []
    assert state(client)["completed_at"]


def test_migration_roundtrip_preserves_records_and_refuses_lossy_downgrade(
    client: TestClient, database_url: str
) -> None:
    initial = first(client)

    def migrate(*arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "alembic", *arguments],
            cwd=BACKEND,
            env={**os.environ, "DATABASE_URL": database_url},
            capture_output=True,
            text=True,
            check=False,
        )

    assert migrate("downgrade", "0002_onboarding_vehicles").returncode == 0
    assert migrate("upgrade", "head").returncode == 0
    assert state(client) == initial
    engine = create_engine(database_url)
    assert {
        fk["name"] for fk in inspect(engine).get_foreign_keys("user_onboarding")
    } >= {"fk_onboarding_first_owner", "fk_onboarding_active_owner"}
    engine.dispose()
    client.delete(f"/api/v1/vehicles/{initial['active_vehicle_id']}", headers=headers())
    result = migrate("downgrade", "0002_onboarding_vehicles")
    assert result.returncode != 0 and "no data was changed" in result.stderr
    assert state(client)["completed_at"] == initial["completed_at"]
    assert state(client)["vehicles"] == []
