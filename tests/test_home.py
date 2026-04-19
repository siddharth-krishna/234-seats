"""Tests for the home page."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.constituency import Constituency
from app.models.election import Election
from app.models.prediction import Prediction
from app.models.result import Result
from app.models.user import User
from app.services.auth import create_session_token, hash_password


@pytest.fixture()
def election(db: Session) -> Election:
    election = Election(name="TN 2026", year=2026, active=True)
    db.add(election)
    db.flush()
    return election


@pytest.fixture()
def user(db: Session) -> User:
    user = User(username="alice", hashed_password=hash_password("pass"))
    db.add(user)
    db.flush()
    return user


def logged_in_client(client: TestClient, user: User) -> TestClient:
    """Set a valid session cookie on the client for the given user."""
    client.cookies.set("session", create_session_token(user.id))
    return client


def test_home_page_shows_constituencies_table(
    client: TestClient, user: User, election: Election, db: Session
) -> None:
    """Home page shows the sortable constituencies table."""
    seat = Constituency(
        election_id=election.id,
        number=1,
        name="Chennai Central",
        district="Chennai",
        predictions_open=True,
    )
    db.add(seat)
    db.commit()
    logged_in_client(client, user)
    response = client.get("/")
    assert response.status_code == 200
    assert "All Constituencies" in response.text
    assert 'href="/seat/' in response.text
    assert "Predicted" in response.text
    assert "TBD" in response.text


def test_home_page_constituencies_table_sorts_by_predicted(
    client: TestClient, user: User, election: Election, db: Session
) -> None:
    """Predicted seats can be sorted to the top."""
    seat_a = Constituency(
        election_id=election.id,
        number=1,
        name="Alpha",
        district="D1",
        predictions_open=True,
    )
    seat_b = Constituency(
        election_id=election.id,
        number=2,
        name="Beta",
        district="D2",
        predictions_open=False,
    )
    db.add_all([seat_a, seat_b])
    db.flush()
    db.add(Prediction(user_id=user.id, constituency_id=seat_b.id, predicted_winner="Someone"))
    db.add(Result(constituency_id=seat_b.id, winner_name="Winner", winner_party="DMK"))
    db.commit()
    logged_in_client(client, user)
    response = client.get("/?seat_sort=predicted&seat_dir=asc")
    alpha_index = response.text.index("Alpha")
    beta_index = response.text.index("Beta")
    assert beta_index < alpha_index
    assert "Winner (DMK)" in response.text
