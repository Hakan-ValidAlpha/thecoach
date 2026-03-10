"""add garmin ids to planned_workouts

Revision ID: b062c64dcedf
Revises: cf653d3edf25
Create Date: 2026-03-10 12:33:57.864254

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b062c64dcedf'
down_revision: Union[str, None] = 'cf653d3edf25'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('planned_workouts', sa.Column('garmin_workout_id', sa.BigInteger(), nullable=True))
    op.add_column('planned_workouts', sa.Column('garmin_schedule_id', sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column('planned_workouts', 'garmin_schedule_id')
    op.drop_column('planned_workouts', 'garmin_workout_id')
