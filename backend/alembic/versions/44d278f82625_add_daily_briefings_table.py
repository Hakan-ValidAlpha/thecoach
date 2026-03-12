"""add daily_briefings table

Revision ID: 44d278f82625
Revises: dc53b291bc8e
Create Date: 2026-03-11 08:31:40.300306

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '44d278f82625'
down_revision: Union[str, None] = 'dc53b291bc8e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('daily_briefings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('changes_made', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('sync_status', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_daily_briefings_date'), 'daily_briefings', ['date'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_daily_briefings_date'), table_name='daily_briefings')
    op.drop_table('daily_briefings')
