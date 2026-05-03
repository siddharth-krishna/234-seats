"""Election model — top-level container for a single election cycle."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.constituency import Constituency
    from app.models.result import ProvisionalResultSet


class Election(Base):
    """A single election cycle (e.g. Tamil Nadu 2026 assembly elections).

    All constituencies, predictions, and results are scoped to an election,
    enabling the app to be reused across multiple elections.
    """

    __tablename__ = "elections"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    year: Mapped[int] = mapped_column(nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    constituencies: Mapped[list[Constituency]] = relationship(
        back_populates="election", cascade="all, delete-orphan"
    )
    provisional_result_sets: Mapped[list[ProvisionalResultSet]] = relationship(
        back_populates="election", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Election id={self.id} name={self.name!r} year={self.year}>"
