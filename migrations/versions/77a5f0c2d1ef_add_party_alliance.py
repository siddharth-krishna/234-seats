"""add party alliance

Revision ID: 77a5f0c2d1ef
Revises: 3c7ddfb9e73c
Create Date: 2026-04-18 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "77a5f0c2d1ef"
down_revision: Union[str, Sequence[str], None] = "3c7ddfb9e73c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("parties", sa.Column("alliance", sa.String(length=100), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("parties", "alliance")
