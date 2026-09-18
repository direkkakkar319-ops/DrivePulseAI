"""Signup, password/Google login, session validation, and logout endpoints."""

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentSession, CurrentUser, Db
from app.models.user import User
from app.schemas.auth import (
    AuthUser,
    Credentials,
    GoogleCredentials,
    Registration,
    SessionResponse,
)
from app.services.auth_service import (
    dummy_hash,
    issue_session,
    password_hasher,
    verify_google_token,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=SessionResponse, status_code=201)
def register(body: Registration, db: Db) -> SessionResponse:
    user = User(email=body.email, password_hash=password_hasher.hash(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "An account already exists. Please log in.") from exc
    return issue_session(db, user)


@router.post("/login", response_model=SessionResponse)
def login(body: Credentials, db: Db) -> SessionResponse:
    user = db.scalar(select(User).where(User.email == body.email))
    hashed = user.password_hash if user and user.password_hash else dummy_hash
    valid = password_hasher.verify(body.password, hashed)
    if not valid or user is None or user.password_hash is None:
        raise HTTPException(401, "Invalid email or password.")
    return issue_session(db, user)


@router.post("/google", response_model=SessionResponse)
def google_login(body: GoogleCredentials, db: Db) -> SessionResponse:
    claims = verify_google_token(body.id_token)
    user = db.scalar(select(User).where(User.google_subject == claims["sub"]))
    if user is None:
        # Never link by email alone: password accounts have not verified ownership.
        user = User(email=claims["email"].lower(), google_subject=claims["sub"])
        db.add(user)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            user = db.scalar(select(User).where(User.google_subject == claims["sub"]))
            if user is None:
                raise HTTPException(
                    409, "An account already uses this email. Use password login."
                ) from exc
    return issue_session(db, user)


@router.get("/me", response_model=AuthUser)
def me(user: CurrentUser) -> User:
    return user


@router.post("/logout", status_code=204)
def logout(db: Db, session: CurrentSession) -> Response:
    db.delete(session)
    db.commit()
    return Response(status_code=204)
