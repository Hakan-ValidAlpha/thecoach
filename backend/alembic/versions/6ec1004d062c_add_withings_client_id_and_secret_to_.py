"""add withings_client_id and secret to settings

Revision ID: 6ec1004d062c
Revises: a5147ec9adc8
Create Date: 2026-03-10 09:26:33.713452

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6ec1004d062c'
down_revision: Union[str, None] = 'a5147ec9adc8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('settings', sa.Column('withings_client_id', sa.String(length=255), nullable=True))
    op.add_column('settings', sa.Column('withings_client_secret', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('settings', 'withings_client_secret')
    op.drop_column('settings', 'withings_client_id')
