"""Password hashing, Google identity verification, and session issuance."""

import hashlib
import secrets
import time

from fastapi import HTTPException
from google.auth.exceptions import TransportError
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import AuthSession, User
from app.schemas.auth import AuthUser, SessionResponse

password_hasher = PasswordHash.recommended()
# Verify a dummy hash for unknown users to avoid a cheap account timing oracle.
dummy_hash = password_hasher.hash(secrets.token_urlsafe(32))


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_session(db: Session, user: User) -> SessionResponse:
    token = secrets.token_urlsafe(32)
    expires_at = int(time.time()) + settings.session_hours * 3600
    db.add(
        AuthSession(
            token_hash=token_digest(token), user_id=user.id, expires_at=expires_at
        )
    )
    db.commit()
    return SessionResponse(
        access_token=token, expires_at=expires_at, user=AuthUser.model_validate(user)
    )


def verify_google_token(token: str) -> dict:
    if not settings.google_web_client_id:
        raise HTTPException(503, "Google sign-in is not configured.")
    try:
        claims = id_token.verify_oauth2_token(
            token, Request(), audience=settings.google_web_client_id
        )
    except TransportError as exc:
        raise HTTPException(
            503, "Google verification is unavailable. Try again."
        ) from exc
    except ValueError as exc:
        raise HTTPException(401, "Invalid Google identity token.") from exc
    if not claims.get("sub") or claims.get("email_verified") is not True:
        raise HTTPException(401, "A verified Google identity is required.")
    if not isinstance(claims.get("email"), str):
        raise HTTPException(401, "Google did not supply an email address.")
    return claims
