"""Strict onboarding/vehicle wire contracts mirrored in mobile and frontend TypeScript."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProfileSetupInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    full_name: str | None = Field(default=None, max_length=120)
    driving_licence: Literal["yes", "no", "prefer-not-to-say"] | None = None


class VehicleInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    powertrain: Literal["ice", "hybrid", "ev"]
    manufacturer: str = Field(min_length=1, max_length=60)
    model: str = Field(min_length=1, max_length=80)
    year: int = Field(strict=True, ge=1886)
    fuel_type: (
        Literal["petrol", "diesel", "cng", "petrol-electric", "diesel-electric"] | None
    ) = None
    nickname: str | None = Field(default=None, max_length=60)

    @model_validator(mode="after")
    def validate_metadata(self) -> "VehicleInput":
        if self.year > datetime.now(UTC).year + 1:
            raise ValueError("Model year must not exceed next year")
        fuels = {
            "ice": {"petrol", "diesel", "cng"},
            "hybrid": {"petrol-electric", "diesel-electric"},
            "ev": {None},
        }
        if self.fuel_type not in fuels[self.powertrain]:
            raise ValueError("Fuel type does not match powertrain")
        self.nickname = self.nickname or None
        return self


class SavedVehicleResponse(VehicleInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    owner_uid: str
    created_at: datetime


class OnboardingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    firebase_uid: str
    full_name: str | None
    driving_licence: Literal["yes", "no", "prefer-not-to-say"] | None
    profile_completed_at: datetime | None
    completed_at: datetime | None
    first_vehicle_id: UUID | None
    active_vehicle_id: UUID | None
    vehicles: list[SavedVehicleResponse]
