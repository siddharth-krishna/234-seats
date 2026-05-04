"""Tests for provisional result entry and display."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.models.candidate import Candidate
from app.models.constituency import Constituency, Party
from app.models.election import Election
from app.models.prediction import Prediction
from app.models.result import (
    ProvisionalResultCandidate,
    ProvisionalResultSeat,
    ProvisionalResultSet,
    Result,
)
from app.models.user import User
from app.services.auth import create_session_token, hash_password
from app.services.scoring import compute_scores


@pytest.fixture()
def election(db: Session) -> Election:
    """Create an active election."""
    election = Election(name="TN 2026", year=2026, active=True)
    db.add(election)
    db.flush()
    return election


@pytest.fixture()
def parties(db: Session) -> list[Party]:
    """Create two parties."""
    dmk = Party(name="DMK", abbreviation="DMK", color_hex="#e63946")
    aiadmk = Party(name="AIADMK", abbreviation="AIADMK", color_hex="#2a9d8f")
    db.add_all([dmk, aiadmk])
    db.flush()
    return [dmk, aiadmk]


@pytest.fixture()
def seat(db: Session, election: Election, parties: list[Party]) -> Constituency:
    """Create a constituency with two candidates."""
    constituency = Constituency(
        election_id=election.id,
        number=1,
        name="Seat A",
        district="D",
        predictions_open=True,
    )
    db.add(constituency)
    db.flush()
    db.add_all(
        [
            Candidate(constituency_id=constituency.id, name="Alice", party_id=parties[0].id),
            Candidate(constituency_id=constituency.id, name="Bob", party_id=parties[1].id),
        ]
    )
    db.flush()
    return constituency


@pytest.fixture()
def admin(db: Session) -> User:
    """Create an admin user."""
    user = User(username="admin", hashed_password=hash_password("pass"), is_admin=True)
    db.add(user)
    db.flush()
    return user


@pytest.fixture()
def user(db: Session) -> User:
    """Create a regular user."""
    user = User(username="alice", hashed_password=hash_password("pass"))
    db.add(user)
    db.flush()
    return user


def auth(client: TestClient, user: User) -> TestClient:
    """Set a session cookie for a user."""
    client.cookies.set("session", create_session_token(user.id))
    return client


def test_admin_results_page_lists_provisional_sets(
    client: TestClient,
    admin: User,
    election: Election,
    seat: Constituency,
    db: Session,
) -> None:
    """Admin can see the provisional results tab."""
    candidates = db.query(Candidate).order_by(Candidate.name).all()
    result_set = ProvisionalResultSet(
        election_id=election.id, counted_at=datetime(2026, 5, 4, 10, 0)
    )
    db.add(result_set)
    db.flush()
    result_set.seat_results.append(
        _seat_result(seat.id, [(candidates[0], 51.0), (candidates[1], 45.0)])
    )
    db.commit()
    auth(client, admin)

    response = client.get("/admin/results")

    assert response.status_code == 200
    assert "Provisional results" in response.text
    assert "2026-05-04 10:00" in response.text


def test_create_provisional_result_set(
    client: TestClient,
    admin: User,
    seat: Constituency,
    db: Session,
) -> None:
    """Admin can save a timestamped provisional result set."""
    db.commit()
    candidates = db.query(Candidate).order_by(Candidate.name).all()
    auth(client, admin)

    response = client.post(
        "/admin/results",
        data={
            "counted_at": "2026-05-04T11:30",
            f"votes_counted_{seat.id}": "12345",
            f"vote_share_{seat.id}_{candidates[0].id}": "48.5",
            f"vote_share_{seat.id}_{candidates[1].id}": "45.2",
        },
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/admin/results"
    result_set = db.query(ProvisionalResultSet).one()
    assert result_set.counted_at == datetime(2026, 5, 4, 11, 30)
    assert len(result_set.seat_results) == 1
    assert result_set.seat_results[0].votes_counted == 12345
    assert len(result_set.seat_results[0].candidate_results) == 2


def test_api_create_provisional_result_set(
    client: TestClient,
    seat: Constituency,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Script API can save scraped provisional results with local candidate matching."""
    monkeypatch.setattr(settings, "provisional_results_api_token", "test-token")
    db.commit()

    response = client.post(
        "/api/provisional-results",
        headers={"X-Provisional-Results-Token": "test-token"},
        json={
            "counted_at": "2026-05-04T12:00:00",
            "seats": [
                {
                    "constituency_number": seat.number,
                    "votes_counted": 10000,
                    "candidates": [
                        {"name": "ALICE.", "party": "DMK", "vote_share": 51.2},
                        {"name": "Bob", "party": "AIADMK", "vote_share": 48.8},
                    ],
                }
            ],
        },
    )

    assert response.status_code == 201
    assert response.json()["seats_imported"] == 1
    assert response.json()["unmatched_candidates"] == []
    result_set = db.query(ProvisionalResultSet).one()
    assert result_set.counted_at == datetime(2026, 5, 4, 12, 0)
    result = result_set.seat_results[0].candidate_results[0]
    assert result.candidate_name == "Alice"
    assert result.candidate_id is not None


def test_api_rejects_invalid_token(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Script API requires the configured token."""
    monkeypatch.setattr(settings, "provisional_results_api_token", "test-token")

    response = client.post(
        "/api/provisional-results",
        headers={"X-Provisional-Results-Token": "wrong"},
        json={"seats": []},
    )

    assert response.status_code == 403


def test_provisional_result_form_only_shows_open_seats(
    client: TestClient,
    admin: User,
    election: Election,
    seat: Constituency,
    db: Session,
) -> None:
    """Provisional result entry is limited to seats still marked open."""
    closed_seat = Constituency(
        election_id=election.id,
        number=2,
        name="Closed Seat",
        district="D",
        predictions_open=False,
    )
    db.add(closed_seat)
    db.commit()
    auth(client, admin)

    response = client.get("/admin/results/new")

    assert response.status_code == 200
    assert seat.name in response.text
    assert "Closed Seat" not in response.text


def test_provisional_result_validation_rejects_bad_values(
    client: TestClient,
    admin: User,
    seat: Constituency,
    db: Session,
) -> None:
    """Votes counted and vote percentages are validated before saving."""
    db.commit()
    candidates = db.query(Candidate).order_by(Candidate.name).all()
    auth(client, admin)

    response = client.post(
        "/admin/results",
        data={
            "counted_at": "2026-05-04T11:30",
            f"votes_counted_{seat.id}": "0",
            f"vote_share_{seat.id}_{candidates[0].id}": "70",
            f"vote_share_{seat.id}_{candidates[1].id}": "35",
        },
    )

    assert response.status_code == 400
    assert "votes counted must be a positive whole number" in response.text
    assert "candidate vote percentages must sum to less than 100%" in response.text
    assert db.query(ProvisionalResultSet).count() == 0


def test_update_provisional_result_set(
    client: TestClient,
    admin: User,
    seat: Constituency,
    db: Session,
) -> None:
    """Admin can update a previously entered provisional result set."""
    db.commit()
    candidates = db.query(Candidate).order_by(Candidate.name).all()
    auth(client, admin)
    client.post(
        "/admin/results",
        data={
            "counted_at": "2026-05-04T11:30",
            f"vote_share_{seat.id}_{candidates[0].id}": "48.5",
            f"vote_share_{seat.id}_{candidates[1].id}": "45.2",
        },
    )
    result_set = db.query(ProvisionalResultSet).one()

    response = client.post(
        f"/admin/results/{result_set.id}",
        data={
            "counted_at": "2026-05-04T12:30",
            f"votes_counted_{seat.id}": "15000",
            f"vote_share_{seat.id}_{candidates[0].id}": "44.0",
            f"vote_share_{seat.id}_{candidates[1].id}": "50.0",
        },
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/admin/results"
    db.refresh(result_set)
    assert result_set.counted_at == datetime(2026, 5, 4, 12, 30)
    assert result_set.seat_results[0].votes_counted == 15000
    shares = {
        candidate_result.candidate_name: candidate_result.vote_share
        for candidate_result in result_set.seat_results[0].candidate_results
    }
    assert shares == {"Alice": 44.0, "Bob": 50.0}


def test_delete_provisional_result_set(
    client: TestClient,
    admin: User,
    election: Election,
    seat: Constituency,
    db: Session,
) -> None:
    """Admin can delete a provisional result set from the results page."""
    candidates = db.query(Candidate).order_by(Candidate.name).all()
    result_set = ProvisionalResultSet(
        election_id=election.id, counted_at=datetime(2026, 5, 4, 10, 0)
    )
    db.add(result_set)
    db.flush()
    result_set.seat_results.append(
        _seat_result(seat.id, [(candidates[0], 51.0), (candidates[1], 45.0)])
    )
    db.commit()
    auth(client, admin)

    response = client.post(f"/admin/results/{result_set.id}/delete")

    assert response.status_code == 302
    assert response.headers["location"] == "/admin/results"
    assert db.query(ProvisionalResultSet).count() == 0


def test_scoring_uses_latest_provisional_winner(
    db: Session,
    election: Election,
    seat: Constituency,
    user: User,
) -> None:
    """Leaderboard scores use the latest provisional winner over official results."""
    candidates = db.query(Candidate).order_by(Candidate.name).all()
    db.add(Result(constituency_id=seat.id, winner_name="Alice", winner_party="DMK"))
    db.add(Prediction(user_id=user.id, constituency_id=seat.id, predicted_winner="Bob"))
    db.flush()
    old_set = ProvisionalResultSet(election_id=election.id, counted_at=datetime(2026, 5, 4, 10, 0))
    new_set = ProvisionalResultSet(election_id=election.id, counted_at=datetime(2026, 5, 4, 11, 0))
    db.add_all([old_set, new_set])
    db.flush()
    old_set.seat_results = []
    new_set.seat_results = []
    old_set.seat_results.append(
        _seat_result(seat.id, [(candidates[0], 51.0), (candidates[1], 45.0)])
    )
    new_set.seat_results.append(
        _seat_result(seat.id, [(candidates[0], 44.0), (candidates[1], 50.0)])
    )
    db.commit()

    scores = {score.username: score for score in compute_scores(db, election.id)}

    assert scores["alice"].correct_seats == 1
    assert scores["alice"].seats_with_results == 1


def test_constituency_page_shows_provisional_table(
    client: TestClient,
    user: User,
    election: Election,
    seat: Constituency,
    db: Session,
) -> None:
    """Seat page displays latest provisional rows with party boxes."""
    candidates = db.query(Candidate).order_by(Candidate.name).all()
    db.add(Prediction(user_id=user.id, constituency_id=seat.id, predicted_winner="Bob"))
    result_set = ProvisionalResultSet(
        election_id=election.id, counted_at=datetime(2026, 5, 4, 13, 0)
    )
    db.add(result_set)
    db.flush()
    result_set.seat_results.append(
        _seat_result(
            seat.id,
            [(candidates[0], 42.0), (candidates[1], 53.0)],
            votes_counted=20000,
        )
    )
    db.commit()
    auth(client, user)

    response = client.get(f"/seat/{seat.id}")

    assert response.status_code == 200
    assert "Provisional result" in response.text
    assert "2026-05-04 13:00" in response.text
    assert "20,000 votes counted" in response.text
    assert "AIADMK" in response.text
    assert response.text.index("Bob") < response.text.index("Alice")


def _seat_result(
    constituency_id: int,
    candidate_shares: list[tuple[Candidate, float]],
    votes_counted: int | None = None,
) -> ProvisionalResultSeat:
    return ProvisionalResultSeat(
        constituency_id=constituency_id,
        votes_counted=votes_counted,
        candidate_results=[
            ProvisionalResultCandidate(
                candidate_id=candidate.id,
                candidate_name=candidate.name,
                party_id=candidate.party_id,
                vote_share=share,
            )
            for candidate, share in candidate_shares
        ],
    )
