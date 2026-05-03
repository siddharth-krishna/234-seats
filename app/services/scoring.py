"""Scoring service: compute per-user prediction accuracy statistics."""

import math
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.constituency import Constituency
from app.models.prediction import Prediction
from app.models.result import ProvisionalResultSeat
from app.models.user import User
from app.services.provisional_results import (
    get_latest_provisional_results_by_constituency,
    provisional_winner,
)


@dataclass
class UserScore:
    """Accuracy statistics for a single user within one election."""

    user_id: int
    username: str
    num_predictions: int
    correct_seats: int
    seats_with_results: int  # predictions where a result has been declared
    vote_share_mae: float | None  # mean absolute error, or None if no data yet
    vote_share_rmse: float | None  # root mean square error, or None if no data yet


@dataclass(frozen=True)
class EffectiveResult:
    """Result data used for scoring, official or latest provisional."""

    winner_name: str
    winner_vote_share: float | None


def compute_scores(db: Session, election_id: int) -> list[UserScore]:
    """Return a UserScore for every user, for the given election.

    Users with no predictions are included with zeroed stats so they appear
    on the leaderboard from the start.
    """
    users = db.query(User).order_by(User.username).all()
    provisional_results = get_latest_provisional_results_by_constituency(db, election_id)
    return [_score_user(db, user, election_id, provisional_results) for user in users]


def _score_user(
    db: Session,
    user: User,
    election_id: int,
    provisional_results: dict[int, ProvisionalResultSeat],
) -> UserScore:
    """Compute the score for a single user."""
    predictions = (
        db.query(Prediction)
        .join(Constituency, Prediction.constituency_id == Constituency.id)
        .filter(Constituency.election_id == election_id, Prediction.user_id == user.id)
        .all()
    )

    correct_seats = 0
    seats_with_results = 0
    errors: list[float] = []

    for pred in predictions:
        result = _effective_result(
            pred.constituency,
            provisional_results.get(pred.constituency_id),
        )
        if result is None:
            continue
        seats_with_results += 1
        if pred.predicted_winner.strip().lower() == result.winner_name.strip().lower():
            correct_seats += 1
        if pred.predicted_vote_share is not None and result.winner_vote_share is not None:
            errors.append(pred.predicted_vote_share - result.winner_vote_share)

    mae = sum(abs(e) for e in errors) / len(errors) if errors else None
    rmse = math.sqrt(sum(e**2 for e in errors) / len(errors)) if errors else None

    return UserScore(
        user_id=user.id,
        username=user.username,
        num_predictions=len(predictions),
        correct_seats=correct_seats,
        seats_with_results=seats_with_results,
        vote_share_mae=round(mae, 2) if mae is not None else None,
        vote_share_rmse=round(rmse, 2) if rmse is not None else None,
    )


def _effective_result(
    constituency: Constituency,
    provisional_result: ProvisionalResultSeat | None,
) -> EffectiveResult | None:
    """Return the latest provisional result for scoring, falling back to official."""
    if provisional_result is not None:
        winner = provisional_winner(provisional_result)
        if winner is None:
            return None
        return EffectiveResult(
            winner_name=winner.candidate_name,
            winner_vote_share=winner.vote_share,
        )

    if constituency.result is None:
        return None
    return EffectiveResult(
        winner_name=constituency.result.winner_name,
        winner_vote_share=constituency.result.winner_vote_share,
    )


# Valid sort keys and their default direction (True = descending)
SORT_KEYS: dict[str, bool] = {
    "username": False,
    "num_predictions": True,
    "correct_seats": True,
    "vote_share_mae": False,  # lower is better
    "vote_share_rmse": False,
}


def sort_scores(
    scores: list[UserScore],
    sort_by: str = "correct_seats",
    descending: bool = True,
) -> list[UserScore]:
    """Sort a list of UserScore objects by the given field.

    Unknown sort keys fall back to the default (correct_seats descending).
    None values are sorted to the end regardless of direction.
    """
    if sort_by not in SORT_KEYS:
        sort_by = "correct_seats"
        descending = True

    if sort_by == "username":
        return sorted(scores, key=lambda s: s.username.lower(), reverse=descending)

    def key(s: UserScore) -> tuple[int, float]:
        val = getattr(s, sort_by)
        # None sorts after all real values
        if val is None:
            return (1, 0.0)
        return (0, -float(val) if descending else float(val))

    return sorted(scores, key=key)
