"""add anthropic_api_key to settings

Revision ID: dc53b291bc8e
Revises: ccba0c8b8df6
Create Date: 2026-03-11 07:38:12.809391

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'dc53b291bc8e'
down_revision: Union[str, None] = 'ccba0c8b8df6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('settings', sa.Column('anthropic_api_key', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('settings', 'anthropic_api_key')
