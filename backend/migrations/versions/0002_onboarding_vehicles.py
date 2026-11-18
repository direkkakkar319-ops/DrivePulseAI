"""Add owner-scoped vehicle metadata and onboarding state without changing users."""

import sqlalchemy as sa

from alembic import op

revision = "0002_onboarding_vehicles"
down_revision = "0001_user_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vehicles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "owner_uid",
            sa.String(128),
            sa.ForeignKey("users.firebase_uid", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("powertrain", sa.String(12), nullable=False),
        sa.Column("manufacturer", sa.String(60), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("fuel_type", sa.String(24)),
        sa.Column("nickname", sa.String(60)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("owner_uid", "id", name="uq_vehicle_owner_id"),
        sa.CheckConstraint(
            "powertrain IN ('ice','hybrid','ev')", name="ck_vehicle_powertrain"
        ),
        sa.CheckConstraint("year >= 1886 AND year <= 9999", name="ck_vehicle_year"),
        sa.CheckConstraint(
            "length(trim(manufacturer)) > 0 AND length(trim(model)) > 0",
            name="ck_vehicle_names",
        ),
        sa.CheckConstraint(
            "(powertrain = 'ev' AND fuel_type IS NULL) OR (powertrain = 'ice' AND fuel_type IS NOT NULL AND fuel_type IN ('petrol','diesel','cng')) OR (powertrain = 'hybrid' AND fuel_type IS NOT NULL AND fuel_type IN ('petrol-electric','diesel-electric'))",
            name="ck_vehicle_fuel",
        ),
    )
    op.create_index("ix_vehicles_owner_uid", "vehicles", ["owner_uid"])
    op.create_table(
        "user_onboarding",
        sa.Column(
            "firebase_uid",
            sa.String(128),
            sa.ForeignKey("users.firebase_uid", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("full_name", sa.String(120)),
        sa.Column("driving_licence", sa.String(24)),
        sa.Column("profile_completed_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("first_vehicle_id", sa.Uuid()),
        sa.Column("active_vehicle_id", sa.Uuid()),
        sa.ForeignKeyConstraint(
            ["firebase_uid", "first_vehicle_id"],
            ["vehicles.owner_uid", "vehicles.id"],
            name="fk_onboarding_first_owner",
        ),
        sa.ForeignKeyConstraint(
            ["firebase_uid", "active_vehicle_id"],
            ["vehicles.owner_uid", "vehicles.id"],
            name="fk_onboarding_active_owner",
        ),
        sa.CheckConstraint(
            "driving_licence IS NULL OR driving_licence IN ('yes','no','prefer-not-to-say')",
            name="ck_onboarding_licence",
        ),
        sa.CheckConstraint(
            "profile_completed_at IS NULL OR (full_name IS NOT NULL AND length(trim(full_name)) > 0)",
            name="ck_onboarding_name",
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR (profile_completed_at IS NOT NULL AND first_vehicle_id IS NOT NULL AND active_vehicle_id IS NOT NULL)",
            name="ck_onboarding_complete",
        ),
    )


def downgrade() -> None:
    op.drop_table("user_onboarding")
    op.drop_index("ix_vehicles_owner_uid", table_name="vehicles")
    op.drop_table("vehicles")
