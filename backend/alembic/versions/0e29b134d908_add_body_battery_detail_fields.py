"""Add body battery detail fields

Revision ID: 0e29b134d908
Revises: 17a973997fc1
Create Date: 2026-03-10 08:52:24.552154

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0e29b134d908'
down_revision: Union[str, None] = '17a973997fc1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('daily_health', sa.Column('body_battery_current', sa.Integer(), nullable=True))
    op.add_column('daily_health', sa.Column('body_battery_charged', sa.Integer(), nullable=True))
    op.add_column('daily_health', sa.Column('body_battery_drained', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('daily_health', 'body_battery_drained')
    op.drop_column('daily_health', 'body_battery_charged')
    op.drop_column('daily_health', 'body_battery_current')
