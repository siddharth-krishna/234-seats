"""Candidate model — a candidate standing in a constituency."""

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


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

    constituency: Mapped["Constituency"] = relationship(back_populates="candidates")  # type: ignore[name-defined]  # noqa: F821
    party: Mapped["Party | None"] = relationship()  # type: ignore[name-defined]  # noqa: F821

    def __repr__(self) -> str:
        return f"<Candidate id={self.id} name={self.name!r}>"
