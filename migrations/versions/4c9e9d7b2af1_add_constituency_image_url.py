"""add constituency image url

Revision ID: 4c9e9d7b2af1
Revises: 77a5f0c2d1ef
Create Date: 2026-04-19 09:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4c9e9d7b2af1"
down_revision: Union[str, Sequence[str], None] = "77a5f0c2d1ef"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("constituencies", sa.Column("image_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("constituencies", "image_url")
