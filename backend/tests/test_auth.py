"""Authentication integration tests against an isolated database."""

import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models.user import AuthSession, User
from app.services import auth_service

CREDS = {"email": "driver@example.com", "password": "a-long-test-password"}


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        app.dependency_overrides[get_db] = lambda: db
        with TestClient(app) as client:
            yield client, db
    app.dependency_overrides.clear()
    engine.dispose()


def headers(response):
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_signup_login_and_logout(client):
    api, db = client
    registered = api.post("/auth/register", json=CREDS)
    assert registered.status_code == 201
    assert registered.headers["cache-control"] == "no-store"
    assert set(registered.json()["user"]) == {"id", "email"}
    assert (
        api.get("/auth/me", headers=headers(registered)).json()["email"]
        == CREDS["email"]
    )
    user = db.scalar(select(User))
    assert user.password_hash != CREDS["password"]
    session = db.scalar(select(AuthSession))
    assert session.token_hash != registered.json()["access_token"]
    logged_in = api.post("/auth/login", json={**CREDS, "email": "DRIVER@example.com"})
    assert logged_in.status_code == 200
    assert logged_in.json()["access_token"] != registered.json()["access_token"]
    assert api.post("/auth/logout", headers=headers(registered)).status_code == 204
    assert api.get("/auth/me", headers=headers(registered)).status_code == 401
    assert api.get("/auth/me", headers=headers(logged_in)).status_code == 200


@pytest.mark.parametrize("email", [CREDS["email"], "missing@example.com"])
def test_wrong_credentials(client, email):
    api, _ = client
    api.post("/auth/register", json=CREDS)
    response = api.post("/auth/login", json={"email": email, "password": "wrong"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_registration_validation_and_duplicate(client):
    api, _ = client
    assert (
        api.post("/auth/register", json={**CREDS, "password": "short"}).status_code
        == 422
    )
    assert api.post("/auth/register", json={**CREDS, "email": "bad"}).status_code == 422
    api.post("/auth/register", json=CREDS)
    assert (
        api.post(
            "/auth/register", json={**CREDS, "email": "DRIVER@example.com"}
        ).status_code
        == 409
    )


def test_protected_endpoint_and_expiry(client):
    api, db = client
    assert api.get("/auth/me").status_code == 401
    assert (
        api.get("/auth/me", headers={"Authorization": "Bearer fake"}).status_code == 401
    )
    response = api.post("/auth/register", json=CREDS)
    session = db.scalar(select(AuthSession))
    session.expires_at = int(time.time()) - 1
    db.commit()
    assert api.get("/auth/me", headers=headers(response)).status_code == 401


def test_google_verified_identity_and_repeat_login(client, monkeypatch):
    api, db = client
    monkeypatch.setattr(settings, "google_web_client_id", "test-client")
    claims = {"sub": "google-subject", "email": CREDS["email"], "email_verified": True}
    with patch.object(
        auth_service.id_token, "verify_oauth2_token", return_value=claims
    ) as verify:
        first = api.post("/auth/google", json={"id_token": "signed-token"})
        second = api.post("/auth/google", json={"id_token": "signed-token"})
    assert first.status_code == second.status_code == 200
    assert first.json()["user"] == second.json()["user"]
    assert verify.call_args.kwargs["audience"] == "test-client"
    assert db.scalar(select(User)).google_subject == "google-subject"
    assert api.post("/auth/login", json=CREDS).status_code == 401


def test_google_does_not_link_unverified_password_account(client, monkeypatch):
    api, _ = client
    api.post("/auth/register", json=CREDS)
    monkeypatch.setattr(settings, "google_web_client_id", "test-client")
    claims = {"sub": "google-subject", "email": CREDS["email"], "email_verified": True}
    with patch.object(
        auth_service.id_token, "verify_oauth2_token", return_value=claims
    ):
        assert api.post("/auth/google", json={"id_token": "token"}).status_code == 409


@pytest.mark.parametrize(
    "claims",
    [
        {"sub": "sub", "email": CREDS["email"], "email_verified": False},
        {"email": CREDS["email"], "email_verified": True},
        {"sub": "sub", "email_verified": True},
    ],
)
def test_google_rejects_incomplete_identity(client, monkeypatch, claims):
    api, _ = client
    monkeypatch.setattr(settings, "google_web_client_id", "test-client")
    with patch.object(
        auth_service.id_token, "verify_oauth2_token", return_value=claims
    ):
        assert api.post("/auth/google", json={"id_token": "token"}).status_code == 401


def test_google_invalid_token_and_missing_config(client, monkeypatch):
    api, _ = client
    monkeypatch.setattr(settings, "google_web_client_id", "")
    assert api.post("/auth/google", json={"id_token": "token"}).status_code == 503
    monkeypatch.setattr(settings, "google_web_client_id", "test-client")
    with patch.object(
        auth_service.id_token, "verify_oauth2_token", side_effect=ValueError
    ):
        assert api.post("/auth/google", json={"id_token": "invalid"}).status_code == 401
