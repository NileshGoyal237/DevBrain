"""add constraints, examples, starter_code to challenges

Revision ID: a1b2c3d4e5f6
Revises: 1a2b3c4d5e6f
Create Date: 2026-05-30 00:21:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '1a2b3c4d5e6f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'challenges',
        sa.Column('constraints', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        'challenges',
        sa.Column('examples', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        'challenges',
        sa.Column('starter_code', sa.Text(), nullable=True, server_default=''),
    )


def downgrade() -> None:
    op.drop_column('challenges', 'starter_code')
    op.drop_column('challenges', 'examples')
    op.drop_column('challenges', 'constraints')
