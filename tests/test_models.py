"""Tests for ORM models and their relationships."""

from sqlalchemy.orm import Session

from app.models.constituency import Constituency, Party
from app.models.election import Election
from app.models.prediction import Prediction
from app.models.result import Result
from app.models.user import User


def make_election(db: Session) -> Election:
    """Create and persist a minimal election."""
    election = Election(name="Tamil Nadu 2026", year=2026, active=True)
    db.add(election)
    db.flush()
    return election


def make_constituency(db: Session, election: Election, number: int = 1) -> Constituency:
    """Create and persist a minimal constituency."""
    c = Constituency(
        election_id=election.id,
        number=number,
        name=f"Constituency {number}",
        district="Test District",
        predictions_open=True,
    )
    db.add(c)
    db.flush()
    return c


def make_user(db: Session, username: str = "alice") -> User:
    """Create and persist a minimal user."""
    user = User(username=username, hashed_password="hashed")
    db.add(user)
    db.flush()
    return user


# ── Election ──────────────────────────────────────────────────────────────────


def test_election_created(db: Session) -> None:
    """Election is persisted and retrievable by id."""
    election = make_election(db)
    db.commit()
    fetched = db.get(Election, election.id)
    assert fetched is not None
    assert fetched.name == "Tamil Nadu 2026"
    assert fetched.active is True


def test_election_constituency_relationship(db: Session) -> None:
    """Election.constituencies returns all child constituencies."""
    election = make_election(db)
    make_constituency(db, election, number=1)
    make_constituency(db, election, number=2)
    db.commit()

    fetched = db.get(Election, election.id)
    assert fetched is not None
    assert len(fetched.constituencies) == 2


# ── Party ─────────────────────────────────────────────────────────────────────


def test_party_created(db: Session) -> None:
    """Party is persisted with required fields."""
    party = Party(name="DMK", abbreviation="DMK", color_hex="#e63946")
    db.add(party)
    db.commit()
    fetched = db.get(Party, party.id)
    assert fetched is not None
    assert fetched.abbreviation == "DMK"


# ── Constituency ──────────────────────────────────────────────────────────────


def test_constituency_created(db: Session) -> None:
    """Constituency is persisted with election relationship."""
    election = make_election(db)
    c = make_constituency(db, election)
    db.commit()
    fetched = db.get(Constituency, c.id)
    assert fetched is not None
    assert fetched.election_id == election.id
    assert fetched.predictions_open is True


# ── User ──────────────────────────────────────────────────────────────────────


def test_user_created(db: Session) -> None:
    """User is persisted with unique username."""
    user = make_user(db)
    db.commit()
    fetched = db.get(User, user.id)
    assert fetched is not None
    assert fetched.username == "alice"
    assert fetched.is_admin is False


# ── Prediction ────────────────────────────────────────────────────────────────


def test_prediction_created(db: Session) -> None:
    """Prediction links user and constituency correctly."""
    election = make_election(db)
    c = make_constituency(db, election)
    user = make_user(db)
    prediction = Prediction(
        user_id=user.id,
        constituency_id=c.id,
        predicted_winner="Candidate A",
        predicted_vote_share=42.5,
        comment="Strong incumbent",
    )
    db.add(prediction)
    db.commit()

    fetched = db.get(Prediction, prediction.id)
    assert fetched is not None
    assert fetched.predicted_winner == "Candidate A"
    assert fetched.predicted_vote_share == 42.5


def test_prediction_unique_per_user_constituency(db: Session) -> None:
    """A user cannot submit two predictions for the same constituency."""
    import pytest
    from sqlalchemy.exc import IntegrityError

    election = make_election(db)
    c = make_constituency(db, election)
    user = make_user(db)

    db.add(Prediction(user_id=user.id, constituency_id=c.id, predicted_winner="A"))
    db.flush()
    db.add(Prediction(user_id=user.id, constituency_id=c.id, predicted_winner="B"))
    with pytest.raises(IntegrityError):
        db.flush()


# ── Result ────────────────────────────────────────────────────────────────────


def test_result_created(db: Session) -> None:
    """Result is persisted and accessible via constituency.result."""
    election = make_election(db)
    c = make_constituency(db, election)
    result = Result(
        constituency_id=c.id,
        winner_name="Candidate A",
        winner_party="DMK",
        winner_vote_share=48.3,
    )
    db.add(result)
    db.commit()

    fetched = db.get(Constituency, c.id)
    assert fetched is not None
    assert fetched.result is not None
    assert fetched.result.winner_name == "Candidate A"
