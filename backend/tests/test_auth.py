"""API authentication failures and the Firebase Admin verification boundary."""

from collections.abc import Iterator
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from firebase_admin import auth
from google.auth.exceptions import DefaultCredentialsError

from app.api import deps
from app.config import Settings
from app.core import firebase
from app.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = Settings(
        _env_file=None,
        database_url="postgresql://test:test@localhost/unused",
        cors_origins=[],
    )
    with TestClient(create_app(settings)) as value:
        yield value


@pytest.mark.parametrize("authorization", [None, "Basic abc", "Bearer"])
def test_missing_bearer_is_401(client: TestClient, authorization: str | None) -> None:
    headers = {"Authorization": authorization} if authorization else {}
    response = client.put("/api/v1/users/me", headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("verified", [False, None, "true", 1])
def test_unverified_claim_cannot_access_storage(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, verified: object
) -> None:
    monkeypatch.setattr(
        deps,
        "verify_token",
        lambda *_: {
            "uid": "one",
            "email": "one@example.com",
            "email_verified": verified,
        },
    )
    response = client.put("/api/v1/users/me", headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


@pytest.mark.parametrize("uid", [None, "", 123, "a" * 129])
def test_invalid_identity_is_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, uid: object
) -> None:
    monkeypatch.setattr(
        deps,
        "verify_token",
        lambda *_: {"uid": uid, "email": "one@example.com", "email_verified": True},
    )
    assert (
        client.get(
            "/api/v1/users/me", headers={"Authorization": "Bearer token"}
        ).status_code
        == 401
    )


@pytest.mark.parametrize(
    "failure",
    [
        auth.InvalidIdTokenError("invalid signature or wrong project"),
        auth.ExpiredIdTokenError("expired", cause=None),
        auth.RevokedIdTokenError("revoked"),
        auth.UserDisabledError("disabled"),
        auth.UserNotFoundError("deleted"),
    ],
)
def test_rejected_tokens_never_reach_database(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    monkeypatch.setattr(firebase, "get_firebase_app", lambda *_: object())
    verifier = Mock(side_effect=failure)
    monkeypatch.setattr(firebase.auth, "verify_id_token", verifier)
    response = client.put(
        "/api/v1/users/me", headers={"Authorization": "Bearer invalid-token"}
    )
    assert response.status_code == 401
    assert "invalid-token" not in response.text
    assert verifier.call_args.kwargs["check_revoked"] is True


def test_verification_uses_configured_project_and_revocation_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = object()
    initialize = Mock(return_value=app)
    verifier = Mock(return_value={"uid": "trusted"})
    monkeypatch.setattr(firebase, "get_firebase_app", initialize)
    monkeypatch.setattr(firebase.auth, "verify_id_token", verifier)
    assert firebase.verify_token("opaque-token", "expected-project") == {
        "uid": "trusted"
    }
    initialize.assert_called_once_with("expected-project")
    verifier.assert_called_once_with("opaque-token", app=app, check_revoked=True)


def test_credentials_failure_is_safe_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        firebase,
        "get_firebase_app",
        Mock(side_effect=DefaultCredentialsError("private server details")),
    )
    response = client.put("/api/v1/users/me", headers={"Authorization": "Bearer token"})
    assert response.status_code == 503
    assert "private server details" not in response.text


def test_emulator_cannot_bypass_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "localhost:9099")
    firebase.get_firebase_app.cache_clear()
    with pytest.raises(RuntimeError, match="emulator mode"):
        firebase.get_firebase_app("test-project")


def test_sqlite_config_is_rejected() -> None:
    with pytest.raises(ValueError, match="DATABASE_URL must use postgresql"):
        Settings(_env_file=None, database_url="sqlite:///old.db")


def test_database_failure_does_not_expose_connection_details(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy.exc import OperationalError

    monkeypatch.setattr(
        deps,
        "verify_token",
        lambda *_: {"uid": "one", "email": "one@example.com", "email_verified": True},
    )

    def unavailable() -> None:
        raise OperationalError("private SQL", {}, Exception("private credentials"))

    client.app.dependency_overrides[deps.get_db] = unavailable
    response = client.put("/api/v1/users/me", headers={"Authorization": "Bearer token"})
    assert response.status_code == 503
    assert response.json() == {"detail": "Profile storage unavailable"}
