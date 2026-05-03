"""Result models for official and provisional election outcomes."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.candidate import Candidate
    from app.models.constituency import Constituency, Party
    from app.models.election import Election


class Result(Base):
    """The official election result for a constituency.

    Entered by an admin after results are declared. One result per
    constituency (enforced by the unique FK on constituency_id).
    """

    __tablename__ = "results"

    id: Mapped[int] = mapped_column(primary_key=True)
    constituency_id: Mapped[int] = mapped_column(
        ForeignKey("constituencies.id"), nullable=False, unique=True, index=True
    )
    winner_name: Mapped[str] = mapped_column(String(200), nullable=False)
    winner_party: Mapped[str] = mapped_column(String(200), nullable=False)
    winner_vote_share: Mapped[float | None] = mapped_column(Float)
    declared_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    constituency: Mapped[Constituency] = relationship(back_populates="result")

    def __repr__(self) -> str:
        return (
            f"<Result id={self.id} constituency_id={self.constituency_id} "
            f"winner={self.winner_name!r}>"
        )


class ProvisionalResultSet(Base):
    """A timestamped snapshot of provisional results entered by an admin."""

    __tablename__ = "provisional_result_sets"

    id: Mapped[int] = mapped_column(primary_key=True)
    election_id: Mapped[int] = mapped_column(ForeignKey("elections.id"), nullable=False, index=True)
    counted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    election: Mapped[Election] = relationship(back_populates="provisional_result_sets")
    seat_results: Mapped[list[ProvisionalResultSeat]] = relationship(
        back_populates="result_set", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<ProvisionalResultSet id={self.id} election_id={self.election_id} "
            f"counted_at={self.counted_at!r}>"
        )


class ProvisionalResultSeat(Base):
    """Provisional result snapshot for one constituency within a result set."""

    __tablename__ = "provisional_result_seats"
    __table_args__ = (
        UniqueConstraint(
            "result_set_id",
            "constituency_id",
            name="uq_provisional_result_seat_set_constituency",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    result_set_id: Mapped[int] = mapped_column(
        ForeignKey("provisional_result_sets.id"), nullable=False, index=True
    )
    constituency_id: Mapped[int] = mapped_column(
        ForeignKey("constituencies.id"), nullable=False, index=True
    )
    votes_counted: Mapped[int | None] = mapped_column(Integer)

    result_set: Mapped[ProvisionalResultSet] = relationship(back_populates="seat_results")
    constituency: Mapped[Constituency] = relationship(back_populates="provisional_result_seats")
    candidate_results: Mapped[list[ProvisionalResultCandidate]] = relationship(
        back_populates="seat_result", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<ProvisionalResultSeat id={self.id} result_set_id={self.result_set_id} "
            f"constituency_id={self.constituency_id}>"
        )


class ProvisionalResultCandidate(Base):
    """Provisional vote-share entry for a candidate in a seat snapshot."""

    __tablename__ = "provisional_result_candidates"
    __table_args__ = (
        UniqueConstraint(
            "seat_result_id",
            "candidate_id",
            name="uq_provisional_result_candidate_seat_candidate",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    seat_result_id: Mapped[int] = mapped_column(
        ForeignKey("provisional_result_seats.id"), nullable=False, index=True
    )
    candidate_id: Mapped[int | None] = mapped_column(ForeignKey("candidates.id"), index=True)
    candidate_name: Mapped[str] = mapped_column(String(200), nullable=False)
    party_id: Mapped[int | None] = mapped_column(ForeignKey("parties.id"))
    vote_share: Mapped[float] = mapped_column(Float, nullable=False)

    seat_result: Mapped[ProvisionalResultSeat] = relationship(back_populates="candidate_results")
    candidate: Mapped[Candidate | None] = relationship()
    party: Mapped[Party | None] = relationship()

    def __repr__(self) -> str:
        return (
            f"<ProvisionalResultCandidate id={self.id} "
            f"candidate_name={self.candidate_name!r} vote_share={self.vote_share}>"
        )
