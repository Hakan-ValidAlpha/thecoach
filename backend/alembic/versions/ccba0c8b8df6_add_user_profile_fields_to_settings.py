"""add user profile fields to settings

Revision ID: ccba0c8b8df6
Revises: b062c64dcedf
Create Date: 2026-03-10 15:44:16.806235

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ccba0c8b8df6'
down_revision: Union[str, None] = 'b062c64dcedf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('settings', sa.Column('user_name', sa.String(length=100), nullable=True))
    op.add_column('settings', sa.Column('age', sa.Integer(), nullable=True))
    op.add_column('settings', sa.Column('running_experience', sa.String(length=50), nullable=True))
    op.add_column('settings', sa.Column('primary_goal', sa.String(length=255), nullable=True))
    op.add_column('settings', sa.Column('goal_race', sa.String(length=255), nullable=True))
    op.add_column('settings', sa.Column('goal_race_date', sa.Date(), nullable=True))
    op.add_column('settings', sa.Column('injuries_notes', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('settings', 'injuries_notes')
    op.drop_column('settings', 'goal_race_date')
    op.drop_column('settings', 'goal_race')
    op.drop_column('settings', 'primary_goal')
    op.drop_column('settings', 'running_experience')
    op.drop_column('settings', 'age')
    op.drop_column('settings', 'user_name')
