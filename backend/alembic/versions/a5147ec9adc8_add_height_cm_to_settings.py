"""add height_cm to settings

Revision ID: a5147ec9adc8
Revises: 0e29b134d908
Create Date: 2026-03-10 09:21:26.977462

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a5147ec9adc8'
down_revision: Union[str, None] = '0e29b134d908'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('settings', sa.Column('height_cm', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('settings', 'height_cm')
