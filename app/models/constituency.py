"""Constituency and Party models."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.candidate import Candidate
    from app.models.election import Election
    from app.models.prediction import Prediction
    from app.models.result import ProvisionalResultSeat, Result


class Party(Base):
    """A political party."""

    __tablename__ = "parties"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    abbreviation: Mapped[str] = mapped_column(String(20), nullable=False)
    alliance: Mapped[str | None] = mapped_column(String(100))
    color_hex: Mapped[str] = mapped_column(String(7), default="#cccccc", nullable=False)

    constituencies: Mapped[list[Constituency]] = relationship(back_populates="current_party_rel")

    def __repr__(self) -> str:
        return f"<Party id={self.id} abbreviation={self.abbreviation!r}>"


class Constituency(Base):
    """A single assembly constituency within an election.

    Stores static details (name, district) as well as the writeup and
    whether predictions are currently open.
    """

    __tablename__ = "constituencies"

    id: Mapped[int] = mapped_column(primary_key=True)
    election_id: Mapped[int] = mapped_column(ForeignKey("elections.id"), nullable=False)
    # Constituency number (1-234 for Tamil Nadu)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    district: Mapped[str] = mapped_column(String(200), nullable=False)
    population: Mapped[int | None] = mapped_column(Integer)
    current_party_id: Mapped[int | None] = mapped_column(ForeignKey("parties.id"))
    writeup: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(500))
    predictions_open: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    election: Mapped[Election] = relationship(back_populates="constituencies")
    current_party_rel: Mapped[Party | None] = relationship(back_populates="constituencies")
    predictions: Mapped[list[Prediction]] = relationship(
        back_populates="constituency", cascade="all, delete-orphan"
    )
    result: Mapped[Result | None] = relationship(
        back_populates="constituency", uselist=False, cascade="all, delete-orphan"
    )
    provisional_result_seats: Mapped[list[ProvisionalResultSeat]] = relationship(
        back_populates="constituency", cascade="all, delete-orphan"
    )
    candidates: Mapped[list[Candidate]] = relationship(
        back_populates="constituency", cascade="all, delete-orphan", order_by="Candidate.name"
    )

    def __repr__(self) -> str:
        return f"<Constituency id={self.id} name={self.name!r}>"
