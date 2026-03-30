"""Prediction model — one user's prediction for one constituency."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.constituency import Constituency
    from app.models.user import User


class Prediction(Base):
    """A single user's prediction for a constituency.

    Each user may submit at most one prediction per constituency (enforced by
    the unique constraint). The prediction can optionally be updated before
    predictions close.
    """

    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint("user_id", "constituency_id", name="uq_prediction_user_constituency"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    constituency_id: Mapped[int] = mapped_column(
        ForeignKey("constituencies.id"), nullable=False, index=True
    )
    predicted_winner: Mapped[str] = mapped_column(String(200), nullable=False)
    predicted_vote_share: Mapped[float | None] = mapped_column(Float)
    comment: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="predictions")
    constituency: Mapped[Constituency] = relationship(back_populates="predictions")

    def __repr__(self) -> str:
        return (
            f"<Prediction id={self.id} user_id={self.user_id} "
            f"constituency_id={self.constituency_id}>"
        )
