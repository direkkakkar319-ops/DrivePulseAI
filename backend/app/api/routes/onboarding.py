"""Verified, owner-scoped onboarding and atomic retry-safe first vehicle creation."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.api.deps import Identity, get_db, require_identity
from app.models.onboarding import UserOnboarding
from app.models.user import UserProfile
from app.models.vehicle import Vehicle
from app.schemas.onboarding import (
    OnboardingResponse,
    ProfileSetupInput,
    SavedVehicleResponse,
    VehicleInput,
)

router = APIRouter(prefix="/api/v1", tags=["onboarding", "vehicles"])


def account_identity(
    identity: Annotated[Identity, Depends(require_identity)],
    expected_uid: Annotated[str, Header(alias="X-Account-UID")],
) -> Identity:
    # The token establishes ownership. This additional precondition stops an old
    # screen's mutation if Firebase changes accounts while its token is loading.
    if expected_uid != identity.uid:
        raise HTTPException(409, "Account changed; reload your account")
    return identity


CurrentIdentity = Annotated[Identity, Depends(account_identity)]
Database = Annotated[Session, Depends(get_db)]


def state_for(identity: Identity, db: Session, *, lock: bool = False) -> UserOnboarding:
    # Create missing rows from verified claims without altering the existing sync
    # contract or copying app profile edits back into Firebase identity fields.
    db.execute(
        insert(UserProfile)
        .values(
            firebase_uid=identity.uid, email=identity.email, username=identity.username
        )
        .on_conflict_do_nothing()
    )
    db.execute(
        insert(UserOnboarding)
        .values(firebase_uid=identity.uid)
        .on_conflict_do_nothing()
    )
    statement = select(UserOnboarding).where(
        UserOnboarding.firebase_uid == identity.uid
    )
    if lock:
        statement = statement.with_for_update()
    return db.scalars(statement).one()


def response_for(
    state: UserOnboarding, db: Session, response: Response
) -> OnboardingResponse:
    response.headers["Cache-Control"] = "no-store"
    vehicles = db.scalars(
        select(Vehicle)
        .where(Vehicle.owner_uid == state.firebase_uid)
        .order_by(Vehicle.created_at, Vehicle.id)
    ).all()
    return OnboardingResponse(
        **{
            field: getattr(state, field)
            for field in OnboardingResponse.model_fields
            if field != "vehicles"
        },
        vehicles=[SavedVehicleResponse.model_validate(vehicle) for vehicle in vehicles],
    )


@router.get("/onboarding", response_model=OnboardingResponse)
def read_onboarding(
    identity: CurrentIdentity, db: Database, response: Response
) -> OnboardingResponse:
    state = state_for(identity, db, lock=True)
    result = response_for(state, db, response)
    db.commit()
    return result


@router.put("/onboarding/profile", response_model=OnboardingResponse)
def save_profile(
    data: ProfileSetupInput, identity: CurrentIdentity, db: Database, response: Response
) -> OnboardingResponse:
    state = state_for(identity, db, lock=True)
    state.full_name = (
        (data.full_name or "").strip()
        or (identity.username or "").strip()
        or identity.email.split("@")[0].strip()
        or "Your profile"
    )[:120]
    state.driving_licence = data.driving_licence or "prefer-not-to-say"
    state.profile_completed_at = state.profile_completed_at or datetime.now(UTC)
    result = response_for(state, db, response)
    db.commit()
    return result


@router.put("/onboarding/first-vehicle", response_model=OnboardingResponse)
def save_first_vehicle(
    data: VehicleInput, identity: CurrentIdentity, db: Database, response: Response
) -> OnboardingResponse:
    state = state_for(identity, db, lock=True)
    if state.profile_completed_at is None:
        raise HTTPException(409, "Complete profile setup first")
    if state.first_vehicle_id is not None:
        existing = db.get(Vehicle, state.first_vehicle_id)
        if existing is None or any(
            getattr(existing, field) != value
            for field, value in data.model_dump().items()
        ):
            raise HTTPException(409, "First vehicle already saved; reload your account")
        # Lost-response retries must not reset a subsequently chosen active vehicle.
        return response_for(state, db, response)
    vehicle = Vehicle(owner_uid=identity.uid, **data.model_dump())
    db.add(vehicle)
    db.flush()
    state.first_vehicle_id = state.active_vehicle_id = vehicle.id
    state.completed_at = datetime.now(UTC)
    # Vehicle, active selection, and completion either all commit or all roll back.
    result = response_for(state, db, response)
    db.commit()
    return result


@router.get("/vehicles", response_model=list[SavedVehicleResponse])
def list_vehicles(
    identity: CurrentIdentity, db: Database, response: Response
) -> list[Vehicle]:
    response.headers["Cache-Control"] = "no-store"
    return list(
        db.scalars(
            select(Vehicle)
            .where(Vehicle.owner_uid == identity.uid)
            .order_by(Vehicle.created_at, Vehicle.id)
        )
    )


@router.post("/vehicles", response_model=SavedVehicleResponse, status_code=201)
def add_vehicle(
    data: VehicleInput, identity: CurrentIdentity, db: Database, response: Response
) -> Vehicle:
    state = state_for(identity, db, lock=True)
    if state.completed_at is None:
        raise HTTPException(409, "Complete first vehicle setup first")
    vehicle = Vehicle(owner_uid=identity.uid, **data.model_dump())
    db.add(vehicle)
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return vehicle


@router.get("/vehicles/{vehicle_id}", response_model=SavedVehicleResponse)
def read_vehicle(
    vehicle_id: UUID, identity: CurrentIdentity, db: Database, response: Response
) -> Vehicle:
    vehicle = db.scalars(
        select(Vehicle).where(
            Vehicle.id == vehicle_id, Vehicle.owner_uid == identity.uid
        )
    ).one_or_none()
    if vehicle is None:
        raise HTTPException(404, "Vehicle not found")
    response.headers["Cache-Control"] = "no-store"
    return vehicle


@router.put("/vehicles/{vehicle_id}/active", response_model=OnboardingResponse)
def select_vehicle(
    vehicle_id: UUID, identity: CurrentIdentity, db: Database, response: Response
) -> OnboardingResponse:
    state = state_for(identity, db, lock=True)
    vehicle = db.scalars(
        select(Vehicle).where(
            Vehicle.id == vehicle_id, Vehicle.owner_uid == identity.uid
        )
    ).one_or_none()
    if vehicle is None:
        raise HTTPException(404, "Vehicle not found")
    if state.completed_at is None:
        raise HTTPException(409, "Complete first vehicle setup first")
    state.active_vehicle_id = vehicle.id
    result = response_for(state, db, response)
    db.commit()
    return result
