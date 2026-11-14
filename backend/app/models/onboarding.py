"""Durable onboarding milestones and owner-constrained first/active vehicle references."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserOnboarding(Base):
    __tablename__ = "user_onboarding"
    __table_args__ = (
        ForeignKeyConstraint(
            ["firebase_uid", "first_vehicle_id"],
            ["vehicles.owner_uid", "vehicles.id"],
            name="fk_onboarding_first_owner",
        ),
        ForeignKeyConstraint(
            ["firebase_uid", "active_vehicle_id"],
            ["vehicles.owner_uid", "vehicles.id"],
            name="fk_onboarding_active_owner",
        ),
        CheckConstraint(
            "driving_licence IS NULL OR driving_licence IN ('yes','no','prefer-not-to-say')",
            name="ck_onboarding_licence",
        ),
        CheckConstraint(
            "profile_completed_at IS NULL OR (full_name IS NOT NULL AND length(trim(full_name)) > 0)",
            name="ck_onboarding_name",
        ),
        CheckConstraint(
            "completed_at IS NULL OR (profile_completed_at IS NOT NULL AND first_vehicle_id IS NOT NULL AND active_vehicle_id IS NOT NULL)",
            name="ck_onboarding_complete",
        ),
    )
    firebase_uid: Mapped[str] = mapped_column(
        ForeignKey("users.firebase_uid", ondelete="CASCADE"), primary_key=True
    )
    full_name: Mapped[str | None] = mapped_column(String(120))
    driving_licence: Mapped[str | None] = mapped_column(String(24))
    profile_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_vehicle_id: Mapped[UUID | None] = mapped_column(Uuid)
    active_vehicle_id: Mapped[UUID | None] = mapped_column(Uuid)
