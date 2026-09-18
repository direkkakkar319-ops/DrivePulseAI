"""Reusable bearer-session authentication for protected API routes."""

import time
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import AuthSession, User
from app.services.auth_service import token_digest

Db = Annotated[Session, Depends(get_db)]
bearer = HTTPBearer(auto_error=False)


def get_session(
    db: Db,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> AuthSession:
    session = (
        db.get(AuthSession, token_digest(credentials.credentials))
        if credentials
        else None
    )
    if session is None or session.expires_at <= int(time.time()):
        raise HTTPException(
            401,
            "Session expired or invalid. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return session


CurrentSession = Annotated[AuthSession, Depends(get_session)]


def get_current_user(db: Db, session: CurrentSession) -> User:
    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(401, "Account no longer exists.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
