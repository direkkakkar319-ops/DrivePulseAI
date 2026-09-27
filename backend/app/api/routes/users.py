"""Read and synchronize only the authenticated user's minimal profile."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.api.deps import Identity, get_db, require_identity
from app.models.user import UserProfile
from app.schemas.user import UserProfileResponse

router = APIRouter(prefix="/api/v1/users", tags=["users"])
CurrentIdentity = Annotated[Identity, Depends(require_identity)]
Database = Annotated[Session, Depends(get_db)]


@router.put("/me", response_model=UserProfileResponse)
def sync_profile(
    identity: CurrentIdentity, db: Database, response: Response
) -> UserProfile:
    # No UID/email/name accepted from the request body. Only verified claims
    # establish identity. Atomic upsert makes retries/concurrent requests safe.
    statement = insert(UserProfile).values(
        firebase_uid=identity.uid, email=identity.email, username=identity.username
    )
    statement = statement.on_conflict_do_update(
        index_elements=[UserProfile.firebase_uid],
        set_={
            "email": statement.excluded.email,
            "username": statement.excluded.username,
            "updated_at": func.now(),
        },
    ).returning(UserProfile)
    profile = db.scalars(statement).one()
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return profile


@router.get("/me", response_model=UserProfileResponse)
def read_profile(
    identity: CurrentIdentity, db: Database, response: Response
) -> UserProfile:
    profile = db.get(UserProfile, identity.uid)
    if profile is None:
        raise HTTPException(404, "Profile has not been synchronized yet")
    response.headers["Cache-Control"] = "no-store"
    return profile
