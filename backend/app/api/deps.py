"""Reusable dependencies enforcing verified Firebase identity and DB session scope."""

from collections.abc import Generator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.firebase import verify_token

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Identity:
    uid: str
    email: str
    username: str | None


def require_identity(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Identity:
    if credentials is None:
        raise HTTPException(
            401, "Bearer token required", headers={"WWW-Authenticate": "Bearer"}
        )
    claims = verify_token(
        credentials.credentials, request.app.state.settings.firebase_project_id
    )
    uid, email, name = claims.get("uid"), claims.get("email"), claims.get("name")
    if not isinstance(uid, str) or not 1 <= len(uid) <= 128:
        raise HTTPException(
            401,
            "Invalid authentication identity",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if claims.get("email_verified") is not True:
        raise HTTPException(403, "Verify your email before using the API")
    if not isinstance(email, str) or not email.strip():
        raise HTTPException(403, "An email address is required")
    return Identity(
        uid=uid, email=email, username=name if isinstance(name, str) else None
    )


def get_db(request: Request) -> Generator[Session, None, None]:
    with Session(request.app.state.engine) as session:
        yield session
