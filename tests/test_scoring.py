"""Tests for the scoring service."""

import math

import pytest
from sqlalchemy.orm import Session

from app.models.constituency import Constituency
from app.models.election import Election
from app.models.prediction import Prediction
from app.models.result import Result
from app.models.user import User
from app.services.scoring import UserScore, compute_scores, sort_scores

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def election(db: Session) -> Election:
    e = Election(name="TN 2026", year=2026, active=True)
    db.add(e)
    db.flush()
    return e


@pytest.fixture()
def seats(db: Session, election: Election) -> list[Constituency]:
    cs = [
        Constituency(election_id=election.id, number=i, name=f"Seat {i}", district="D")
        for i in range(1, 4)
    ]
    db.add_all(cs)
    db.flush()
    return cs


@pytest.fixture()
def users(db: Session) -> list[User]:
    us = [User(username=f"user{i}", hashed_password="x") for i in range(1, 3)]
    db.add_all(us)
    db.flush()
    return us


def add_result(db: Session, seat: Constituency, winner: str, share: float) -> Result:
    r = Result(
        constituency_id=seat.id,
        winner_name=winner,
        winner_party="DMK",
        winner_vote_share=share,
    )
    db.add(r)
    db.flush()
    return r


# ── Scoring tests ─────────────────────────────────────────────────────────────


def test_no_predictions(db: Session, election: Election, users: list[User]) -> None:
    """Users with no predictions score zero across the board."""
    scores = compute_scores(db, election.id)
    assert len(scores) == 2
    for s in scores:
        assert s.num_predictions == 0
        assert s.correct_seats == 0
        assert s.vote_share_mae is None
        assert s.vote_share_rmse is None


def test_correct_seat_counted(
    db: Session, election: Election, seats: list[Constituency], users: list[User]
) -> None:
    """A prediction matching the result winner increments correct_seats."""
    add_result(db, seats[0], "Alice", 48.0)
    db.add(
        Prediction(
            user_id=users[0].id,
            constituency_id=seats[0].id,
            predicted_winner="Alice",
            predicted_vote_share=47.0,
        )
    )
    db.commit()

    scores = {s.username: s for s in compute_scores(db, election.id)}
    assert scores["user1"].correct_seats == 1
    assert scores["user1"].seats_with_results == 1
    assert scores["user2"].correct_seats == 0


def test_wrong_prediction_not_counted(
    db: Session, election: Election, seats: list[Constituency], users: list[User]
) -> None:
    """A wrong prediction does not increment correct_seats."""
    add_result(db, seats[0], "Alice", 48.0)
    db.add(
        Prediction(
            user_id=users[0].id,
            constituency_id=seats[0].id,
            predicted_winner="Bob",
            predicted_vote_share=45.0,
        )
    )
    db.commit()

    scores = {s.username: s for s in compute_scores(db, election.id)}
    assert scores["user1"].correct_seats == 0
    assert scores["user1"].seats_with_results == 1


def test_vote_share_mae_rmse(
    db: Session, election: Election, seats: list[Constituency], users: list[User]
) -> None:
    """MAE and RMSE are computed correctly over multiple results."""
    # errors: +2, -4  → MAE = 3.0, RMSE = sqrt((4+16)/2) = sqrt(10)
    add_result(db, seats[0], "A", 40.0)
    add_result(db, seats[1], "B", 50.0)
    db.add_all([
        Prediction(
            user_id=users[0].id,
            constituency_id=seats[0].id,
            predicted_winner="A",
            predicted_vote_share=42.0,
        ),
        Prediction(
            user_id=users[0].id,
            constituency_id=seats[1].id,
            predicted_winner="B",
            predicted_vote_share=46.0,
        ),
    ])
    db.commit()

    scores = {s.username: s for s in compute_scores(db, election.id)}
    s = scores["user1"]
    assert s.vote_share_mae == round(3.0, 2)
    assert s.vote_share_rmse == round(math.sqrt(10), 2)


def test_no_result_does_not_count(
    db: Session, election: Election, seats: list[Constituency], users: list[User]
) -> None:
    """Predictions for seats without results don't affect seats_with_results."""
    db.add(
        Prediction(
            user_id=users[0].id,
            constituency_id=seats[0].id,
            predicted_winner="Alice",
        )
    )
    db.commit()

    scores = {s.username: s for s in compute_scores(db, election.id)}
    s = scores["user1"]
    assert s.num_predictions == 1
    assert s.seats_with_results == 0
    assert s.vote_share_mae is None


def test_case_insensitive_winner_match(
    db: Session, election: Election, seats: list[Constituency], users: list[User]
) -> None:
    """Winner name comparison is case-insensitive."""
    add_result(db, seats[0], "Alice Kumar", 48.0)
    db.add(
        Prediction(
            user_id=users[0].id,
            constituency_id=seats[0].id,
            predicted_winner="alice kumar",
        )
    )
    db.commit()

    scores = {s.username: s for s in compute_scores(db, election.id)}
    assert scores["user1"].correct_seats == 1


# ── Sorting tests ─────────────────────────────────────────────────────────────


def test_sort_by_correct_seats_desc() -> None:
    """sort_scores orders by correct_seats descending by default."""
    s1 = UserScore(1, "alice", 3, 2, 2, 1.0, 1.0)
    s2 = UserScore(2, "bob", 3, 5, 5, 2.0, 2.0)
    result = sort_scores([s1, s2], sort_by="correct_seats", descending=True)
    assert result[0].username == "bob"


def test_sort_none_values_last() -> None:
    """Users with None MAE sort after users with a value."""
    s1 = UserScore(1, "alice", 1, 0, 0, None, None)
    s2 = UserScore(2, "bob", 1, 0, 1, 2.0, 2.0)
    result = sort_scores([s1, s2], sort_by="vote_share_mae", descending=False)
    assert result[0].username == "bob"
    assert result[1].username == "alice"


def test_sort_unknown_key_falls_back() -> None:
    """An unknown sort key falls back to correct_seats descending."""
    s1 = UserScore(1, "alice", 0, 1, 1, None, None)
    s2 = UserScore(2, "bob", 0, 3, 3, None, None)
    result = sort_scores([s1, s2], sort_by="nonexistent", descending=False)
    assert result[0].username == "bob"
