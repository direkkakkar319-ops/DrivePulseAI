"""Preserve completed onboarding when a user removes saved vehicles."""

from alembic import op
from sqlalchemy import text

revision = "0003_garage_lifecycle"
down_revision = "0002_onboarding_vehicles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_onboarding_complete", "user_onboarding", type_="check")
    op.create_check_constraint(
        "ck_onboarding_complete",
        "user_onboarding",
        "completed_at IS NULL OR profile_completed_at IS NOT NULL",
    )


def downgrade() -> None:
    # Never discard completion or invent a first vehicle to satisfy the old schema.
    incompatible = (
        op.get_bind()
        .execute(
            text(
                "SELECT count(*) FROM user_onboarding WHERE completed_at IS NOT NULL "
                "AND (first_vehicle_id IS NULL OR active_vehicle_id IS NULL)"
            )
        )
        .scalar_one()
    )
    if incompatible:
        raise RuntimeError(
            "Cannot downgrade: completed accounts have removed vehicle references; no data was changed."
        )
    op.drop_constraint("ck_onboarding_complete", "user_onboarding", type_="check")
    op.create_check_constraint(
        "ck_onboarding_complete",
        "user_onboarding",
        "completed_at IS NULL OR (profile_completed_at IS NOT NULL AND first_vehicle_id IS NOT NULL AND active_vehicle_id IS NOT NULL)",
    )
