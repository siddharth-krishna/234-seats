"""Helpers for provisional result snapshots."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session, selectinload

from app.models.candidate import Candidate
from app.models.constituency import Constituency
from app.models.result import (
    ProvisionalResultCandidate,
    ProvisionalResultSeat,
    ProvisionalResultSet,
)

if TYPE_CHECKING:
    from app.models.election import Election


class ProvisionalResultValidationError(ValueError):
    """Raised when provisional result form input is invalid."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("\n".join(errors))


def default_counted_at() -> datetime:
    """Return the default timestamp for a new provisional result set."""
    return datetime.now().replace(second=0, microsecond=0)


def datetime_local_value(value: datetime) -> str:
    """Format a datetime for an HTML datetime-local input."""
    return value.strftime("%Y-%m-%dT%H:%M")


def get_result_form_constituencies(
    db: Session,
    election_id: int,
) -> list[Constituency]:
    """Return seats that should appear on a provisional result form."""
    return (
        db.query(Constituency)
        .options(selectinload(Constituency.candidates).selectinload(Candidate.party))
        .filter(Constituency.election_id == election_id, Constituency.predictions_open.is_(True))
        .order_by(Constituency.number)
        .all()
    )


def get_latest_provisional_result_set(
    db: Session,
    election_id: int,
) -> ProvisionalResultSet | None:
    """Return the latest provisional result set for an election."""
    return (
        db.query(ProvisionalResultSet)
        .filter_by(election_id=election_id)
        .order_by(ProvisionalResultSet.counted_at.desc(), ProvisionalResultSet.id.desc())
        .first()
    )


def get_latest_provisional_results_by_constituency(
    db: Session,
    election_id: int,
) -> dict[int, ProvisionalResultSeat]:
    """Return latest-set provisional seat results keyed by constituency id."""
    latest_set = get_latest_provisional_result_set(db, election_id)
    if latest_set is None:
        return {}
    return {seat.constituency_id: seat for seat in latest_set.seat_results}


def get_latest_provisional_result_for_constituency(
    db: Session,
    constituency_id: int,
) -> ProvisionalResultSeat | None:
    """Return the most recent provisional result entered for a constituency."""
    return (
        db.query(ProvisionalResultSeat)
        .join(ProvisionalResultSet)
        .filter(ProvisionalResultSeat.constituency_id == constituency_id)
        .order_by(ProvisionalResultSet.counted_at.desc(), ProvisionalResultSet.id.desc())
        .first()
    )


def provisional_winner(
    seat_result: ProvisionalResultSeat,
) -> ProvisionalResultCandidate | None:
    """Return the candidate currently leading a provisional seat result."""
    if not seat_result.candidate_results:
        return None
    return max(seat_result.candidate_results, key=lambda result: result.vote_share)


def create_provisional_result_set(
    db: Session,
    election: Election,
    form: Mapping[str, object],
    constituencies: list[Constituency],
) -> ProvisionalResultSet:
    """Create a provisional result set from submitted form data."""
    counted_at = _parse_counted_at(_form_value(form, "counted_at"))
    seat_results = _build_seat_results(form, constituencies)
    result_set = ProvisionalResultSet(
        election_id=election.id,
        counted_at=counted_at,
        seat_results=seat_results,
    )
    db.add(result_set)
    db.commit()
    db.refresh(result_set)
    return result_set


def update_provisional_result_set(
    db: Session,
    result_set: ProvisionalResultSet,
    form: Mapping[str, object],
    constituencies: list[Constituency],
) -> ProvisionalResultSet:
    """Update an existing provisional result set from submitted form data."""
    counted_at = _parse_counted_at(_form_value(form, "counted_at"))
    seat_results = _build_seat_results(form, constituencies)
    result_set.counted_at = counted_at
    result_set.seat_results.clear()
    db.flush()
    result_set.seat_results = seat_results
    db.commit()
    db.refresh(result_set)
    return result_set


def delete_provisional_result_set(
    db: Session,
    result_set: ProvisionalResultSet,
) -> None:
    """Delete a provisional result set and its dependent seat rows."""
    db.delete(result_set)
    db.commit()


def _build_seat_results(
    form: Mapping[str, object],
    constituencies: list[Constituency],
) -> list[ProvisionalResultSeat]:
    """Build provisional seat rows from form data after validating input."""
    errors: list[str] = []
    seat_results: list[ProvisionalResultSeat] = []

    for constituency in constituencies:
        seat_label = f"{constituency.number}. {constituency.name}"
        votes_counted = _parse_optional_int(
            _form_value(form, f"votes_counted_{constituency.id}"),
            f"{seat_label}: votes counted must be a positive whole number.",
            errors,
        )
        total_vote_share = 0.0
        candidate_results: list[ProvisionalResultCandidate] = []

        for candidate in constituency.candidates:
            vote_share = _parse_optional_float(
                _form_value(form, f"vote_share_{constituency.id}_{candidate.id}"),
                f"{seat_label}: {candidate.name}'s vote percentage must be between 0 and 100.",
                errors,
            )
            if vote_share is None:
                continue
            total_vote_share += vote_share
            candidate_results.append(
                ProvisionalResultCandidate(
                    candidate_id=candidate.id,
                    candidate_name=candidate.name,
                    party_id=candidate.party_id,
                    vote_share=vote_share,
                )
            )

        if total_vote_share >= 100:
            errors.append(f"{seat_label}: candidate vote percentages must sum to less than 100%.")

        if votes_counted is None and not candidate_results:
            continue

        seat_results.append(
            ProvisionalResultSeat(
                constituency_id=constituency.id,
                votes_counted=votes_counted,
                candidate_results=candidate_results,
            )
        )

    if errors:
        raise ProvisionalResultValidationError(errors)

    return seat_results


def _form_value(form: Mapping[str, object], key: str) -> str:
    """Return a stripped string value from form data."""
    value = form.get(key, "")
    return str(value).strip()


def _parse_counted_at(raw: str) -> datetime:
    """Parse a datetime-local value, falling back to now for blank input."""
    if not raw:
        return default_counted_at()
    try:
        return datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ProvisionalResultValidationError(["Enter a valid results timestamp."]) from exc


def _parse_optional_float(raw: str, error_message: str, errors: list[str]) -> float | None:
    """Parse an optional percentage value."""
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        errors.append(error_message)
        return None
    if value < 0 or value > 100:
        errors.append(error_message)
        return None
    return value


def _parse_optional_int(raw: str, error_message: str, errors: list[str]) -> int | None:
    """Parse an optional integer value."""
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        errors.append(error_message)
        return None
    if value <= 0:
        errors.append(error_message)
        return None
    return value
