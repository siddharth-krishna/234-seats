"""Machine-facing API routes for scripts and integrations."""

from datetime import datetime
from secrets import compare_digest

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.election import Election
from app.services.provisional_results import (
    ProvisionalCandidateInput,
    ProvisionalResultValidationError,
    ProvisionalSeatInput,
    create_provisional_result_set_from_api,
    default_counted_at,
)

router = APIRouter(prefix="/api")


class ProvisionalCandidatePayload(BaseModel):
    """Candidate result row submitted by the provisional-results scraper."""

    name: str
    party: str
    vote_share: float = Field(ge=0, le=100)


class ProvisionalSeatPayload(BaseModel):
    """Constituency result row submitted by the provisional-results scraper."""

    constituency_number: int = Field(gt=0, le=234)
    votes_counted: int | None = Field(default=None, gt=0)
    candidates: list[ProvisionalCandidatePayload]


class ProvisionalResultsPayload(BaseModel):
    """A timestamped provisional result snapshot."""

    counted_at: datetime | None = None
    seats: list[ProvisionalSeatPayload]


class ProvisionalResultsResponse(BaseModel):
    """Summary returned after a provisional result snapshot is stored."""

    result_set_id: int
    counted_at: datetime
    seats_imported: int
    candidates_imported: int
    unmatched_candidates: list[str]


def _require_api_token(
    token: str | None = Header(default=None, alias="X-Provisional-Results-Token"),
) -> None:
    """Require the configured provisional-results API token."""
    expected = settings.provisional_results_api_token
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Provisional results API token is not configured.",
        )
    if token is None or not compare_digest(token, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API token.")


def _get_active_election_or_404(db: Session) -> Election:
    """Return the active election or raise 404."""
    election = db.query(Election).filter_by(active=True).first()
    if election is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active election")
    return election


@router.post(
    "/provisional-results",
    response_model=ProvisionalResultsResponse,
    dependencies=[Depends(_require_api_token)],
    status_code=status.HTTP_201_CREATED,
)
def create_provisional_results_snapshot(
    payload: ProvisionalResultsPayload,
    db: Session = Depends(get_db),
) -> ProvisionalResultsResponse:
    """Create a provisional result set from a script-submitted snapshot."""
    election = _get_active_election_or_404(db)
    seats = [
        ProvisionalSeatInput(
            constituency_number=seat.constituency_number,
            votes_counted=seat.votes_counted,
            candidates=[
                ProvisionalCandidateInput(
                    name=candidate.name,
                    party=candidate.party,
                    vote_share=candidate.vote_share,
                )
                for candidate in seat.candidates
            ],
        )
        for seat in payload.seats
    ]
    try:
        result = create_provisional_result_set_from_api(
            db,
            election,
            payload.counted_at or default_counted_at(),
            seats,
        )
    except ProvisionalResultValidationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.errors,
        ) from exc
    return ProvisionalResultsResponse(
        result_set_id=result.result_set.id,
        counted_at=result.result_set.counted_at,
        seats_imported=result.seats_imported,
        candidates_imported=result.candidates_imported,
        unmatched_candidates=result.unmatched_candidates,
    )
