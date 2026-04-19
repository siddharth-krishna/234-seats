"""drop current mla

Revision ID: 8a4c7c181b0f
Revises: 4c9e9d7b2af1
Create Date: 2026-04-19 09:50:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8a4c7c181b0f"
down_revision: Union[str, Sequence[str], None] = "4c9e9d7b2af1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column("constituencies", "current_mla")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "constituencies",
        sa.Column("current_mla", sa.String(length=200), nullable=True),
    )
