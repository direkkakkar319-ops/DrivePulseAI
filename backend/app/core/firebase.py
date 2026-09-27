"""Verify Firebase ID tokens using Admin SDK signatures, claims, and revocation checks."""

import os
from functools import lru_cache
from threading import Lock
from typing import Any

import firebase_admin
from fastapi import HTTPException
from firebase_admin import auth, credentials
from google.auth.exceptions import GoogleAuthError

_initialization_lock = Lock()


@lru_cache
def get_firebase_app(project_id: str) -> firebase_admin.App:
    # Never accept unsigned emulator tokens in this server implementation.
    if os.getenv("FIREBASE_AUTH_EMULATOR_HOST"):
        raise RuntimeError("Firebase Auth emulator mode is not enabled for this server")
    with _initialization_lock:
        name = f"drivepulse-api-{project_id}"
        try:
            return firebase_admin.get_app(name)
        except ValueError:
            return firebase_admin.initialize_app(
                credentials.ApplicationDefault(),
                {"projectId": project_id, "httpTimeout": 10},
                name=name,
            )


def verify_token(token: str, project_id: str) -> dict[str, Any]:
    try:
        return auth.verify_id_token(
            token, app=get_firebase_app(project_id), check_revoked=True
        )
    except (
        auth.InvalidIdTokenError,
        auth.RevokedIdTokenError,
        auth.UserDisabledError,
        auth.UserNotFoundError,
    ):
        raise HTTPException(
            401,
            "Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except (GoogleAuthError, auth.CertificateFetchError, ValueError, RuntimeError):
        # Credential/configuration/network failures must not accept a token or
        # expose server credentials and SDK exception text to a client.
        raise HTTPException(503, "Authentication service unavailable") from None
    except firebase_admin.exceptions.FirebaseError:
        raise HTTPException(503, "Authentication service unavailable") from None
