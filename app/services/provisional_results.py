"""Helpers for provisional result snapshots."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
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


@dataclass(frozen=True)
class ProvisionalCandidateInput:
    """A candidate row submitted by an external provisional-results source."""

    name: str
    party: str
    vote_share: float


@dataclass(frozen=True)
class ProvisionalSeatInput:
    """A seat row submitted by an external provisional-results source."""

    constituency_number: int
    candidates: list[ProvisionalCandidateInput]
    votes_counted: int | None = None


@dataclass(frozen=True)
class ProvisionalApiResult:
    """Summary of a provisional-results API import."""

    result_set: ProvisionalResultSet
    seats_imported: int
    candidates_imported: int
    unmatched_candidates: list[str]


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


def create_provisional_result_set_from_api(
    db: Session,
    election: Election,
    counted_at: datetime,
    seats: list[ProvisionalSeatInput],
) -> ProvisionalApiResult:
    """Create a provisional result set from external scraped result rows."""
    constituencies = get_result_form_constituencies(db, election.id)
    constituencies_by_number = {
        constituency.number: constituency for constituency in constituencies
    }
    errors: list[str] = []
    seat_results: list[ProvisionalResultSeat] = []
    unmatched_candidates: list[str] = []
    candidates_imported = 0

    for seat in seats:
        constituency = constituencies_by_number.get(seat.constituency_number)
        if constituency is None:
            errors.append(f"Constituency #{seat.constituency_number} is not open for results.")
            continue

        seat_label = f"{constituency.number}. {constituency.name}"
        if seat.votes_counted is not None and seat.votes_counted <= 0:
            errors.append(f"{seat_label}: votes counted must be a positive whole number.")

        candidate_results: list[ProvisionalResultCandidate] = []
        matched_candidate_ids: set[int] = set()
        for row in seat.candidates:
            if row.vote_share < 0 or row.vote_share > 100:
                errors.append(
                    f"{seat_label}: {row.name}'s vote percentage must be between 0 and 100."
                )
                continue

            candidate = _match_candidate(constituency, row.name, row.party)
            if candidate is not None and candidate.id in matched_candidate_ids:
                candidate = None

            if candidate is None:
                unmatched_candidates.append(f"{seat_label}: {row.name} ({row.party})")
                candidate_results.append(
                    ProvisionalResultCandidate(
                        candidate_id=None,
                        candidate_name=row.name,
                        party_id=_match_party_id(constituency, row.party),
                        vote_share=row.vote_share,
                    )
                )
            else:
                matched_candidate_ids.add(candidate.id)
                candidate_results.append(
                    ProvisionalResultCandidate(
                        candidate_id=candidate.id,
                        candidate_name=candidate.name,
                        party_id=candidate.party_id,
                        vote_share=row.vote_share,
                    )
                )

        if seat.votes_counted is None and not candidate_results:
            continue

        candidates_imported += len(candidate_results)
        seat_results.append(
            ProvisionalResultSeat(
                constituency_id=constituency.id,
                votes_counted=seat.votes_counted,
                candidate_results=candidate_results,
            )
        )

    if errors:
        raise ProvisionalResultValidationError(errors)

    result_set = ProvisionalResultSet(
        election_id=election.id,
        counted_at=counted_at,
        seat_results=seat_results,
    )
    db.add(result_set)
    db.commit()
    db.refresh(result_set)
    return ProvisionalApiResult(
        result_set=result_set,
        seats_imported=len(seat_results),
        candidates_imported=candidates_imported,
        unmatched_candidates=unmatched_candidates,
    )


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


_NAME_PUNCTUATION = re.compile(r"[^a-z0-9]+")


def _normalise_candidate_name(name: str) -> str:
    """Return a punctuation-insensitive candidate name for ECI matching."""
    return _NAME_PUNCTUATION.sub("", name.lower())


def _normalise_party(party: str) -> str:
    """Return a comparable party abbreviation/name."""
    return party.strip().lower().replace(".", "")


def _match_party_id(constituency: Constituency, party_name: str) -> int | None:
    """Return a local party ID matching an external party label in a constituency."""
    target = _normalise_party(party_name)
    if not target:
        return None
    for candidate in constituency.candidates:
        party = candidate.party
        if party is None:
            continue
        if target in {_normalise_party(party.name), _normalise_party(party.abbreviation)}:
            return party.id
    return None


def _match_candidate(
    constituency: Constituency,
    external_name: str,
    external_party: str,
) -> Candidate | None:
    """Match an external candidate row to a local candidate for a constituency."""
    party_matches = [
        candidate
        for candidate in constituency.candidates
        if candidate.party is not None
        and _normalise_party(external_party)
        in {
            _normalise_party(candidate.party.name),
            _normalise_party(candidate.party.abbreviation),
        }
    ]
    if len(party_matches) == 1:
        return party_matches[0]

    target = _normalise_candidate_name(external_name)
    for candidate in constituency.candidates:
        if _normalise_candidate_name(candidate.name) == target:
            return candidate

    if not party_matches:
        return None

    scored = [
        (
            SequenceMatcher(None, _normalise_candidate_name(candidate.name), target).ratio(),
            candidate,
        )
        for candidate in party_matches
    ]
    if not scored:
        return None
    score, candidate = max(scored, key=lambda item: item[0])
    return candidate if score >= 0.86 else None
