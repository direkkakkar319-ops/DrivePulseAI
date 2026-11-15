"""Account-owned vehicle metadata; contains no telemetry or dataset associations."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Vehicle(Base):
    __tablename__ = "vehicles"
    __table_args__ = (
        UniqueConstraint("owner_uid", "id", name="uq_vehicle_owner_id"),
        CheckConstraint(
            "powertrain IN ('ice','hybrid','ev')", name="ck_vehicle_powertrain"
        ),
        CheckConstraint("year >= 1886 AND year <= 9999", name="ck_vehicle_year"),
        CheckConstraint(
            "length(trim(manufacturer)) > 0 AND length(trim(model)) > 0",
            name="ck_vehicle_names",
        ),
        CheckConstraint(
            "(powertrain = 'ev' AND fuel_type IS NULL) OR (powertrain = 'ice' AND fuel_type IS NOT NULL AND fuel_type IN ('petrol','diesel','cng')) OR (powertrain = 'hybrid' AND fuel_type IS NOT NULL AND fuel_type IN ('petrol-electric','diesel-electric'))",
            name="ck_vehicle_fuel",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_uid: Mapped[str] = mapped_column(
        ForeignKey("users.firebase_uid", ondelete="CASCADE"), index=True
    )
    powertrain: Mapped[str] = mapped_column(String(12))
    manufacturer: Mapped[str] = mapped_column(String(60))
    model: Mapped[str] = mapped_column(String(80))
    year: Mapped[int] = mapped_column(Integer)
    fuel_type: Mapped[str | None] = mapped_column(String(24))
    nickname: Mapped[str | None] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
