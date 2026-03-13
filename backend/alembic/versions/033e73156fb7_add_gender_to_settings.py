"""add_gender_to_settings

Revision ID: 033e73156fb7
Revises: 44d278f82625
Create Date: 2026-03-13 09:21:02.520717

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '033e73156fb7'
down_revision: Union[str, None] = '44d278f82625'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('settings', sa.Column('gender', sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.drop_column('settings', 'gender')
