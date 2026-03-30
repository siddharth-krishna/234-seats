"""Result model — actual election outcome for a constituency."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.constituency import Constituency


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
