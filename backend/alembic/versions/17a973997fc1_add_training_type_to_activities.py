"""Add training_type to activities

Revision ID: 17a973997fc1
Revises: 002
Create Date: 2026-03-10 08:43:10.062204

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '17a973997fc1'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('activities', sa.Column('training_type', sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column('activities', 'training_type')
