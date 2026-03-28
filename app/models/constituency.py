"""Constituency and Party models."""

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Party(Base):
    """A political party."""

    __tablename__ = "parties"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    abbreviation: Mapped[str] = mapped_column(String(20), nullable=False)
    color_hex: Mapped[str] = mapped_column(String(7), default="#cccccc", nullable=False)

    constituencies: Mapped[list["Constituency"]] = relationship(back_populates="current_party_rel")

    def __repr__(self) -> str:
        return f"<Party id={self.id} abbreviation={self.abbreviation!r}>"


class Constituency(Base):
    """A single assembly constituency within an election.

    Stores static details (name, district, current MLA) as well as the
    writeup and whether predictions are currently open.
    """

    __tablename__ = "constituencies"

    id: Mapped[int] = mapped_column(primary_key=True)
    election_id: Mapped[int] = mapped_column(ForeignKey("elections.id"), nullable=False)
    # Constituency number (1-234 for Tamil Nadu)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    district: Mapped[str] = mapped_column(String(200), nullable=False)
    population: Mapped[int | None] = mapped_column(Integer)
    current_mla: Mapped[str | None] = mapped_column(String(200))
    current_party_id: Mapped[int | None] = mapped_column(ForeignKey("parties.id"))
    writeup: Mapped[str | None] = mapped_column(Text)
    predictions_open: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    election: Mapped["Election"] = relationship(back_populates="constituencies")  # type: ignore[name-defined]  # noqa: F821
    current_party_rel: Mapped["Party | None"] = relationship(back_populates="constituencies")
    predictions: Mapped[list["Prediction"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="constituency", cascade="all, delete-orphan"
    )
    result: Mapped["Result | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="constituency", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Constituency id={self.id} name={self.name!r}>"
