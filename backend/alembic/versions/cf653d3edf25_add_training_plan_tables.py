"""add training plan tables

Revision ID: cf653d3edf25
Revises: 30b516bd89a8
Create Date: 2026-03-10 11:32:21.930149

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'cf653d3edf25'
down_revision: Union[str, None] = '30b516bd89a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('training_plans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('goal', sa.String(length=255), nullable=True),
        sa.Column('goal_date', sa.Date(), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('training_phases',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plan_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('phase_type', sa.String(length=50), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['plan_id'], ['training_plans.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('planned_workouts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plan_id', sa.Integer(), nullable=False),
        sa.Column('phase_id', sa.Integer(), nullable=True),
        sa.Column('scheduled_date', sa.Date(), nullable=False),
        sa.Column('workout_type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('target_distance_meters', sa.Float(), nullable=True),
        sa.Column('target_duration_seconds', sa.Float(), nullable=True),
        sa.Column('target_pace_min_per_km', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('completed_activity_id', sa.Integer(), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['completed_activity_id'], ['activities.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['phase_id'], ['training_phases.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['plan_id'], ['training_plans.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_planned_workouts_scheduled_date', 'planned_workouts', ['scheduled_date'])


def downgrade() -> None:
    op.drop_index('ix_planned_workouts_scheduled_date', table_name='planned_workouts')
    op.drop_table('planned_workouts')
    op.drop_table('training_phases')
    op.drop_table('training_plans')
