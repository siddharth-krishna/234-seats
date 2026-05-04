"""Tests for the home page."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.constituency import Constituency, Party
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


def test_home_page_shows_prediction_label_and_result_match_marker(
    client: TestClient, user: User, election: Election, db: Session
) -> None:
    """Home page shows predicted candidates and marks matching results."""
    party = Party(name="DMK", abbreviation="DMK", alliance="SPA", color_hex="#e63946")
    seat_correct = Constituency(
        election_id=election.id,
        number=1,
        name="Correct Seat",
        district="D1",
        predictions_open=True,
    )
    seat_wrong = Constituency(
        election_id=election.id,
        number=2,
        name="Wrong Seat",
        district="D2",
        predictions_open=False,
    )
    db.add_all([party, seat_correct, seat_wrong])
    db.flush()
    db.add_all(
        [
            Candidate(constituency_id=seat_correct.id, name="Alice Kumar", party_id=party.id),
            Candidate(constituency_id=seat_wrong.id, name="Charlie Rao", party_id=party.id),
            Prediction(
                user_id=user.id,
                constituency_id=seat_correct.id,
                predicted_winner="Alice Kumar",
            ),
            Prediction(
                user_id=user.id,
                constituency_id=seat_wrong.id,
                predicted_winner="Charlie Rao",
            ),
            Result(
                constituency_id=seat_correct.id,
                winner_name="Alice Kumar",
                winner_party="DMK",
            ),
            Result(
                constituency_id=seat_wrong.id,
                winner_name="Bob",
                winner_party="AIADMK",
            ),
        ]
    )
    db.commit()
    logged_in_client(client, user)

    response = client.get("/")

    assert "Alice Kumar (DMK)" in response.text
    assert "Charlie Rao (DMK)" in response.text
    assert "✓" in response.text
    assert "✗" in response.text


def test_home_page_constituencies_default_sort_prioritizes_actionable_seats(
    client: TestClient, user: User, election: Election, db: Session
) -> None:
    """Default constituency sort shows open unpredicted seats first."""
    open_predicted = Constituency(
        election_id=election.id,
        number=1,
        name="Beta Open Predicted",
        district="D1",
        predictions_open=True,
    )
    closed_unpredicted = Constituency(
        election_id=election.id,
        number=2,
        name="Alpha Closed Unpredicted",
        district="D2",
        predictions_open=False,
    )
    open_unpredicted_b = Constituency(
        election_id=election.id,
        number=3,
        name="Zeta Open Unpredicted",
        district="D3",
        predictions_open=True,
    )
    open_unpredicted_a = Constituency(
        election_id=election.id,
        number=4,
        name="Alpha Open Unpredicted",
        district="D4",
        predictions_open=True,
    )
    db.add_all([open_predicted, closed_unpredicted, open_unpredicted_b, open_unpredicted_a])
    db.flush()
    db.add(
        Prediction(
            user_id=user.id,
            constituency_id=open_predicted.id,
            predicted_winner="Someone",
        )
    )
    db.commit()
    logged_in_client(client, user)

    response = client.get("/")

    assert response.text.index("Alpha Open Unpredicted") < response.text.index(
        "Zeta Open Unpredicted"
    )
    assert response.text.index("Zeta Open Unpredicted") < response.text.index("Beta Open Predicted")
    assert response.text.index("Beta Open Predicted") < response.text.index(
        "Alpha Closed Unpredicted"
    )
