"""Add timeseries and polyline columns to activities

Revision ID: 002
Revises: 001
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("activities", sa.Column("timeseries_json", sa.JSON(), nullable=True))
    op.add_column("activities", sa.Column("polyline_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("activities", "polyline_json")
    op.drop_column("activities", "timeseries_json")
