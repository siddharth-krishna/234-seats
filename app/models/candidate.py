"""Candidate model — a candidate standing in a constituency."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.constituency import Constituency, Party


class Candidate(Base):
    """A candidate standing in a specific constituency.

    Candidates are entered by admins before predictions open. They drive the
    dropdowns on the prediction form and the result entry form.
    """

    __tablename__ = "candidates"
    __table_args__ = (
        UniqueConstraint("constituency_id", "name", name="uq_candidate_constituency_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    constituency_id: Mapped[int] = mapped_column(
        ForeignKey("constituencies.id"), nullable=False, index=True
    )
    party_id: Mapped[int | None] = mapped_column(ForeignKey("parties.id"))
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    constituency: Mapped[Constituency] = relationship(back_populates="candidates")
    party: Mapped[Party | None] = relationship()

    def __repr__(self) -> str:
        return f"<Candidate id={self.id} name={self.name!r}>"
