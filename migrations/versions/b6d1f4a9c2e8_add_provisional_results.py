"""add provisional results

Revision ID: b6d1f4a9c2e8
Revises: 8a4c7c181b0f
Create Date: 2026-05-03 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b6d1f4a9c2e8"
down_revision: Union[str, Sequence[str], None] = "8a4c7c181b0f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "provisional_result_sets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("election_id", sa.Integer(), nullable=False),
        sa.Column("counted_at", sa.DateTime(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["election_id"], ["elections.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_provisional_result_sets_counted_at"),
        "provisional_result_sets",
        ["counted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provisional_result_sets_election_id"),
        "provisional_result_sets",
        ["election_id"],
        unique=False,
    )
    op.create_table(
        "provisional_result_seats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("result_set_id", sa.Integer(), nullable=False),
        sa.Column("constituency_id", sa.Integer(), nullable=False),
        sa.Column("votes_counted", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["constituency_id"], ["constituencies.id"]),
        sa.ForeignKeyConstraint(["result_set_id"], ["provisional_result_sets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "result_set_id",
            "constituency_id",
            name="uq_provisional_result_seat_set_constituency",
        ),
    )
    op.create_index(
        op.f("ix_provisional_result_seats_constituency_id"),
        "provisional_result_seats",
        ["constituency_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provisional_result_seats_result_set_id"),
        "provisional_result_seats",
        ["result_set_id"],
        unique=False,
    )
    op.create_table(
        "provisional_result_candidates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("seat_result_id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=True),
        sa.Column("candidate_name", sa.String(length=200), nullable=False),
        sa.Column("party_id", sa.Integer(), nullable=True),
        sa.Column("vote_share", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["party_id"], ["parties.id"]),
        sa.ForeignKeyConstraint(["seat_result_id"], ["provisional_result_seats.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "seat_result_id",
            "candidate_id",
            name="uq_provisional_result_candidate_seat_candidate",
        ),
    )
    op.create_index(
        op.f("ix_provisional_result_candidates_candidate_id"),
        "provisional_result_candidates",
        ["candidate_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provisional_result_candidates_seat_result_id"),
        "provisional_result_candidates",
        ["seat_result_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_provisional_result_candidates_seat_result_id"),
        table_name="provisional_result_candidates",
    )
    op.drop_index(
        op.f("ix_provisional_result_candidates_candidate_id"),
        table_name="provisional_result_candidates",
    )
    op.drop_table("provisional_result_candidates")
    op.drop_index(
        op.f("ix_provisional_result_seats_result_set_id"),
        table_name="provisional_result_seats",
    )
    op.drop_index(
        op.f("ix_provisional_result_seats_constituency_id"),
        table_name="provisional_result_seats",
    )
    op.drop_table("provisional_result_seats")
    op.drop_index(
        op.f("ix_provisional_result_sets_election_id"),
        table_name="provisional_result_sets",
    )
    op.drop_index(
        op.f("ix_provisional_result_sets_counted_at"),
        table_name="provisional_result_sets",
    )
    op.drop_table("provisional_result_sets")
