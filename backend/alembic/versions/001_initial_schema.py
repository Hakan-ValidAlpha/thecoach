"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Settings table (single row)
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), primary_key=True, default=1),
        sa.Column("garmin_email", sa.String(255), nullable=True),
        sa.Column("garmin_password", sa.String(255), nullable=True),
        sa.Column("withings_access_token", sa.String(1024), nullable=True),
        sa.Column("withings_refresh_token", sa.String(1024), nullable=True),
        sa.Column("withings_token_expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_garmin_sync", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_withings_sync", sa.DateTime(timezone=True), nullable=True),
    )

    # Activities table
    op.create_table(
        "activities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("garmin_activity_id", sa.BigInteger(), unique=True, nullable=False),
        sa.Column("activity_type", sa.String(100), nullable=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("distance_meters", sa.Float(), nullable=True),
        sa.Column("avg_pace_min_per_km", sa.Float(), nullable=True),
        sa.Column("avg_heart_rate", sa.Integer(), nullable=True),
        sa.Column("max_heart_rate", sa.Integer(), nullable=True),
        sa.Column("calories", sa.Integer(), nullable=True),
        sa.Column("avg_cadence", sa.Float(), nullable=True),
        sa.Column("elevation_gain", sa.Float(), nullable=True),
        sa.Column("training_effect_aerobic", sa.Float(), nullable=True),
        sa.Column("training_effect_anaerobic", sa.Float(), nullable=True),
        sa.Column("vo2max_estimate", sa.Float(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
    )
    op.create_index("ix_activities_garmin_activity_id", "activities", ["garmin_activity_id"])
    op.create_index("ix_activities_started_at", "activities", ["started_at"])

    # Activity splits table
    op.create_table(
        "activity_splits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "activity_id",
            sa.Integer(),
            sa.ForeignKey("activities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("split_number", sa.Integer(), nullable=False),
        sa.Column("distance_meters", sa.Float(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("avg_pace_min_per_km", sa.Float(), nullable=True),
        sa.Column("avg_heart_rate", sa.Integer(), nullable=True),
    )

    # Daily health table
    op.create_table(
        "daily_health",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("date", sa.Date(), unique=True, nullable=False),
        sa.Column("resting_heart_rate", sa.Integer(), nullable=True),
        sa.Column("hrv_weekly_avg", sa.Float(), nullable=True),
        sa.Column("hrv_last_night", sa.Float(), nullable=True),
        sa.Column("stress_avg", sa.Integer(), nullable=True),
        sa.Column("stress_max", sa.Integer(), nullable=True),
        sa.Column("body_battery_high", sa.Integer(), nullable=True),
        sa.Column("body_battery_low", sa.Integer(), nullable=True),
        sa.Column("sleep_score", sa.Integer(), nullable=True),
        sa.Column("sleep_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("deep_sleep_seconds", sa.Integer(), nullable=True),
        sa.Column("light_sleep_seconds", sa.Integer(), nullable=True),
        sa.Column("rem_sleep_seconds", sa.Integer(), nullable=True),
        sa.Column("awake_seconds", sa.Integer(), nullable=True),
        sa.Column("steps", sa.Integer(), nullable=True),
        sa.Column("training_readiness", sa.Integer(), nullable=True),
        sa.Column("vo2max", sa.Float(), nullable=True),
        sa.Column("intensity_minutes", sa.Integer(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
    )
    op.create_index("ix_daily_health_date", "daily_health", ["date"])

    # Body composition table
    op.create_table(
        "body_composition",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(50), nullable=False, server_default="garmin"),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("fat_mass_kg", sa.Float(), nullable=True),
        sa.Column("fat_percent", sa.Float(), nullable=True),
        sa.Column("muscle_mass_kg", sa.Float(), nullable=True),
        sa.Column("bone_mass_kg", sa.Float(), nullable=True),
        sa.Column("bmi", sa.Float(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
    )
    op.create_index("ix_body_composition_measured_at", "body_composition", ["measured_at"])


def downgrade() -> None:
    op.drop_table("body_composition")
    op.drop_table("daily_health")
    op.drop_table("activity_splits")
    op.drop_table("activities")
    op.drop_table("settings")
