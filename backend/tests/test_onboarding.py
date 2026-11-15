"""Real PostgreSQL onboarding ownership, transactions, validation, and retry safety."""

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
import test_user_profiles as profile_tests
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.api import deps
from app.config import Settings
from app.main import create_app

pytestmark = pytest.mark.postgres


@pytest.fixture(scope="module")
def database_url() -> str:
    return profile_tests.database_url.__wrapped__()


VEHICLE = {
    "powertrain": "ev",
    "manufacturer": "Any Brand",
    "model": "Model One",
    "year": 2024,
    "fuel_type": None,
    "nickname": None,
}


def headers(uid: str = "alice") -> dict[str, str]:
    return {"Authorization": f"Bearer {uid}", "X-Account-UID": uid}


@pytest.fixture
def client(database_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE user_onboarding, vehicles, users"))
    engine.dispose()
    monkeypatch.setattr(
        deps,
        "verify_token",
        lambda token, _: {
            "uid": token,
            "email": f"{token}@example.com",
            "name": f"Account {token}",
            "email_verified": True,
        },
    )
    with TestClient(
        create_app(Settings(_env_file=None, database_url=database_url))
    ) as value:
        yield value


def profile(client: TestClient, uid: str = "alice") -> dict:
    result = client.put(
        "/api/v1/onboarding/profile",
        headers=headers(uid),
        json={"full_name": "Chosen name", "driving_licence": "no"},
    )
    assert result.status_code == 200
    return result.json()


def first(client: TestClient, uid: str = "alice") -> dict:
    profile(client, uid)
    result = client.put(
        "/api/v1/onboarding/first-vehicle", headers=headers(uid), json=VEHICLE
    )
    assert result.status_code == 200
    return result.json()


def test_resume_and_identity_sync_do_not_overwrite_app_name(client: TestClient) -> None:
    initial = client.get("/api/v1/onboarding", headers=headers()).json()
    assert initial["profile_completed_at"] is None and initial["completed_at"] is None
    partial = profile(client)
    assert partial["full_name"] == "Chosen name" and partial["driving_licence"] == "no"
    assert partial["profile_completed_at"] and partial["completed_at"] is None
    client.put("/api/v1/users/me", headers=headers())
    assert (
        client.get("/api/v1/users/me", headers=headers()).json()["username"]
        == "Account alice"
    )
    assert client.get("/api/v1/onboarding", headers=headers()).json() == partial
    complete = first(client)
    assert (
        complete["completed_at"]
        and complete["first_vehicle_id"] == complete["active_vehicle_id"]
    )
    assert len(complete["vehicles"]) == 1
    assert client.get("/api/v1/onboarding", headers=headers()).json() == complete
    assert (
        client.get("/api/v1/vehicles", headers=headers()).json() == complete["vehicles"]
    )


def test_blank_profile_uses_existing_identity_and_skip_is_complete(
    client: TestClient,
) -> None:
    result = client.put("/api/v1/onboarding/profile", headers=headers(), json={}).json()
    assert result["full_name"] == "Account alice"
    assert result["driving_licence"] == "prefer-not-to-say"
    assert result["profile_completed_at"] and not result["completed_at"]


def test_edit_completed_profile_preserves_milestones_identity_and_vehicles(
    client: TestClient,
) -> None:
    original = first(client)
    updated = client.put(
        "/api/v1/onboarding/profile",
        headers=headers(),
        json={"full_name": "  Edited profile name  ", "driving_licence": "no"},
    )
    assert updated.status_code == 200
    saved = updated.json()
    assert saved["full_name"] == "Edited profile name"
    for field in (
        "firebase_uid",
        "driving_licence",
        "profile_completed_at",
        "completed_at",
        "first_vehicle_id",
        "active_vehicle_id",
        "vehicles",
    ):
        assert saved[field] == original[field]
    assert client.get("/api/v1/onboarding", headers=headers()).json() == saved
    assert (
        client.get("/api/v1/users/me", headers=headers()).json()["username"]
        == "Account alice"
    )
    invalid = client.put(
        "/api/v1/onboarding/profile",
        headers=headers(),
        json={"full_name": "x" * 121, "driving_licence": "no"},
    )
    assert invalid.status_code == 422
    assert client.get("/api/v1/onboarding", headers=headers()).json() == saved


def test_email_fallback_when_firebase_has_no_name(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        deps,
        "verify_token",
        lambda *_: {
            "uid": "alice",
            "email": "emailname@example.com",
            "email_verified": True,
        },
    )
    assert (
        client.put("/api/v1/onboarding/profile", headers=headers(), json={}).json()[
            "full_name"
        ]
        == "emailname"
    )


def test_vehicle_requires_profile_and_failure_does_not_complete(
    client: TestClient,
) -> None:
    assert (
        client.put(
            "/api/v1/onboarding/first-vehicle", headers=headers(), json=VEHICLE
        ).status_code
        == 409
    )
    state = client.get("/api/v1/onboarding", headers=headers()).json()
    assert state["completed_at"] is None and state["vehicles"] == []


def test_concurrent_duplicate_first_vehicle_requests_are_atomic(
    client: TestClient,
) -> None:
    profile(client)

    def save(_: int) -> dict:
        result = client.put(
            "/api/v1/onboarding/first-vehicle", headers=headers(), json=VEHICLE
        )
        assert result.status_code == 200
        return result.json()

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(save, range(12)))
    assert len({result["first_vehicle_id"] for result in results}) == 1
    assert all(
        len(result["vehicles"]) == 1 and result["completed_at"] for result in results
    )
    assert (
        client.put(
            "/api/v1/onboarding/first-vehicle",
            headers=headers(),
            json={**VEHICLE, "model": "Different"},
        ).status_code
        == 409
    )


def test_active_vehicle_persists_and_retry_does_not_reset_it(
    client: TestClient,
) -> None:
    first_state = first(client)
    second = client.post(
        "/api/v1/vehicles", headers=headers(), json={**VEHICLE, "model": "Second"}
    )
    assert second.status_code == 201
    selected = client.put(
        f"/api/v1/vehicles/{second.json()['id']}/active", headers=headers()
    ).json()
    assert selected["active_vehicle_id"] == second.json()["id"]
    retry = client.put(
        "/api/v1/onboarding/first-vehicle", headers=headers(), json=VEHICLE
    ).json()
    assert retry["active_vehicle_id"] == second.json()["id"]
    assert retry["first_vehicle_id"] == first_state["first_vehicle_id"]
    assert (
        client.get("/api/v1/onboarding", headers=headers()).json()["active_vehicle_id"]
        == second.json()["id"]
    )


def test_vehicle_ownership_and_expected_account_precondition(
    client: TestClient,
) -> None:
    state = first(client)
    foreign = state["first_vehicle_id"]
    assert client.get("/api/v1/vehicles", headers=headers("bob")).json() == []
    assert (
        client.get(f"/api/v1/vehicles/{foreign}", headers=headers("bob")).status_code
        == 404
    )
    assert (
        client.put(
            f"/api/v1/vehicles/{foreign}/active", headers=headers("bob")
        ).status_code
        == 404
    )
    assert (
        client.put(f"/api/v1/vehicles/{uuid4()}/active", headers=headers()).status_code
        == 404
    )
    assert (
        client.put(
            "/api/v1/onboarding/profile",
            headers={**headers("bob"), "X-Account-UID": "alice"},
            json={"full_name": "Stale draft"},
        ).status_code
        == 409
    )
    assert (
        client.get("/api/v1/onboarding", headers=headers("bob")).json()[
            "profile_completed_at"
        ]
        is None
    )


def test_database_rejects_cross_account_active_reference(
    client: TestClient, database_url: str
) -> None:
    alice, bob = first(client), first(client, "bob")
    engine = create_engine(database_url)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE user_onboarding SET active_vehicle_id = :vehicle WHERE firebase_uid = 'alice'"
            ),
            {"vehicle": bob["active_vehicle_id"]},
        )
    engine.dispose()
    assert (
        client.get("/api/v1/onboarding", headers=headers()).json()["active_vehicle_id"]
        == alice["active_vehicle_id"]
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"manufacturer": " "},
        {"model": ""},
        {"year": 1885},
        {"year": 9999},
        {"year": "2024"},
        {"powertrain": "hydrogen"},
        {"fuel_type": "petrol"},
        {"powertrain": "ice", "fuel_type": None},
        {"powertrain": "hybrid", "fuel_type": "diesel"},
        {"owner_uid": "victim"},
        {"nickname": "x" * 61},
    ],
)
def test_vehicle_validation_does_not_advance_state(
    client: TestClient, overrides: dict
) -> None:
    profile(client)
    assert (
        client.put(
            "/api/v1/onboarding/first-vehicle",
            headers=headers(),
            json={**VEHICLE, **overrides},
        ).status_code
        == 422
    )
    state = client.get("/api/v1/onboarding", headers=headers()).json()
    assert not state["completed_at"] and not state["vehicles"]


@pytest.mark.parametrize(
    "powertrain,fuel",
    [
        ("ice", "petrol"),
        ("ice", "diesel"),
        ("ice", "cng"),
        ("hybrid", "petrol-electric"),
        ("hybrid", "diesel-electric"),
        ("ev", None),
    ],
)
def test_supported_powertrains(
    client: TestClient, powertrain: str, fuel: str | None
) -> None:
    profile(client)
    assert (
        client.put(
            "/api/v1/onboarding/first-vehicle",
            headers=headers(),
            json={**VEHICLE, "powertrain": powertrain, "fuel_type": fuel},
        ).status_code
        == 200
    )


def test_photo_and_foreign_profile_fields_are_not_accepted(client: TestClient) -> None:
    for data in [
        {"photo": "file:///private.jpg"},
        {"firebase_uid": "victim"},
        {"driving_licence": "invalid"},
    ]:
        assert (
            client.put(
                "/api/v1/onboarding/profile", headers=headers(), json=data
            ).status_code
            == 422
        )


def test_commit_failure_rolls_back_vehicle_and_completion(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile(client)

    def fail(*_: object) -> None:
        raise OperationalError("commit", {}, Exception("private database detail"))

    with monkeypatch.context() as patch:
        patch.setattr(Session, "commit", fail)
        result = client.put(
            "/api/v1/onboarding/first-vehicle", headers=headers(), json=VEHICLE
        )
        assert result.status_code == 503 and "private" not in result.text
    state = client.get("/api/v1/onboarding", headers=headers()).json()
    assert (
        state["vehicles"] == []
        and state["active_vehicle_id"] is None
        and state["completed_at"] is None
    )
    assert (
        client.put(
            "/api/v1/onboarding/first-vehicle", headers=headers(), json=VEHICLE
        ).status_code
        == 200
    )


def test_new_endpoints_require_verified_firebase_identity(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert client.get("/api/v1/onboarding").status_code == 401
    monkeypatch.setattr(
        deps,
        "verify_token",
        lambda *_: {
            "uid": "alice",
            "email": "alice@example.com",
            "email_verified": False,
        },
    )
    assert client.get("/api/v1/onboarding", headers=headers()).status_code == 403
    assert (
        client.put("/api/v1/onboarding/profile", headers=headers(), json={}).status_code
        == 403
    )
    assert (
        client.put(
            "/api/v1/onboarding/first-vehicle", headers=headers(), json=VEHICLE
        ).status_code
        == 403
    )
