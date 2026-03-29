"""Tests for candidate management and candidate-driven dropdowns."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.constituency import Constituency, Party
from app.models.election import Election
from app.models.user import User
from app.services.auth import create_session_token, hash_password

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def election(db: Session) -> Election:
    e = Election(name="TN 2026", year=2026, active=True)
    db.add(e)
    db.flush()
    return e


@pytest.fixture()
def seat(db: Session, election: Election) -> Constituency:
    c = Constituency(
        election_id=election.id, number=1, name="Seat A", district="D", predictions_open=True
    )
    db.add(c)
    db.flush()
    return c


@pytest.fixture()
def party(db: Session) -> Party:
    p = Party(name="DMK", abbreviation="DMK", color_hex="#e63946")
    db.add(p)
    db.flush()
    return p


@pytest.fixture()
def admin(db: Session) -> User:
    u = User(username="admin", hashed_password=hash_password("pass"), is_admin=True)
    db.add(u)
    db.flush()
    return u


@pytest.fixture()
def user(db: Session) -> User:
    u = User(username="alice", hashed_password=hash_password("pass"))
    db.add(u)
    db.flush()
    return u


def auth(client: TestClient, u: User) -> TestClient:
    client.cookies.set("session", create_session_token(u.id))
    return client


# ── Add / remove candidates ────────────────────────────────────────────────────


def test_add_candidate_with_party(
    client: TestClient, admin: User, seat: Constituency, party: Party, db: Session
) -> None:
    db.commit()
    auth(client, admin)
    r = client.post(
        f"/admin/seat/{seat.id}/candidates",
        data={"name": "Alice Kumar", "party_id": str(party.id)},
    )
    assert r.status_code == 302
    cand = db.query(Candidate).filter_by(constituency_id=seat.id).first()
    assert cand is not None
    assert cand.name == "Alice Kumar"
    assert cand.party_id == party.id


def test_add_candidate_without_party(
    client: TestClient, admin: User, seat: Constituency, db: Session
) -> None:
    db.commit()
    auth(client, admin)
    client.post(
        f"/admin/seat/{seat.id}/candidates", data={"name": "Independent Joe", "party_id": ""}
    )
    cand = db.query(Candidate).filter_by(name="Independent Joe").first()
    assert cand is not None
    assert cand.party_id is None


def test_delete_candidate(client: TestClient, admin: User, seat: Constituency, db: Session) -> None:
    cand = Candidate(constituency_id=seat.id, name="Bob")
    db.add(cand)
    db.commit()
    auth(client, admin)
    r = client.post(f"/admin/seat/{seat.id}/candidates/{cand.id}/delete")
    assert r.status_code == 302
    assert db.get(Candidate, cand.id) is None


def test_delete_candidate_wrong_seat_returns_404(
    client: TestClient, admin: User, election: Election, seat: Constituency, db: Session
) -> None:
    other = Constituency(election_id=election.id, number=2, name="Seat B", district="D")
    db.add(other)
    db.flush()
    cand = Candidate(constituency_id=other.id, name="Bob")
    db.add(cand)
    db.commit()
    auth(client, admin)
    # Try to delete a candidate that belongs to a different seat
    r = client.post(f"/admin/seat/{seat.id}/candidates/{cand.id}/delete")
    assert r.status_code == 404


def test_add_candidate_requires_admin(
    client: TestClient, user: User, seat: Constituency, db: Session
) -> None:
    db.commit()
    auth(client, user)
    assert (
        client.post(
            f"/admin/seat/{seat.id}/candidates", data={"name": "X", "party_id": ""}
        ).status_code
        == 403
    )


# ── Dropdown on prediction form ────────────────────────────────────────────────


def test_prediction_form_shows_dropdown_when_candidates_exist(
    client: TestClient, user: User, seat: Constituency, party: Party, db: Session
) -> None:
    """When candidates are registered, prediction form shows a <select>."""
    db.add(Candidate(constituency_id=seat.id, name="Alice Kumar", party_id=party.id))
    db.commit()
    auth(client, user)
    r = client.get(f"/seat/{seat.id}")
    assert r.status_code == 200
    assert "<select" in r.text
    assert "Alice Kumar" in r.text
    assert "DMK" in r.text


def test_prediction_form_shows_text_input_without_candidates(
    client: TestClient, user: User, seat: Constituency, db: Session
) -> None:
    """Without candidates the form falls back to a free-text input."""
    db.commit()
    auth(client, user)
    r = client.get(f"/seat/{seat.id}")
    assert 'type="text"' in r.text
    assert "<select" not in r.text


# ── Dropdown on admin result form ──────────────────────────────────────────────


def test_admin_seat_shows_candidate_dropdown_for_result(
    client: TestClient, admin: User, seat: Constituency, party: Party, db: Session
) -> None:
    """Admin result form shows candidate dropdown when candidates exist."""
    db.add(Candidate(constituency_id=seat.id, name="Alice Kumar", party_id=party.id))
    db.commit()
    auth(client, admin)
    r = client.get(f"/admin/seat/{seat.id}")
    assert r.status_code == 200
    # Should have a select for winner_name
    assert 'name="winner_name"' in r.text
    assert "Alice Kumar" in r.text


def test_admin_seat_shows_text_input_without_candidates(
    client: TestClient, admin: User, seat: Constituency, db: Session
) -> None:
    """Admin result form falls back to text inputs when no candidates."""
    db.commit()
    auth(client, admin)
    r = client.get(f"/admin/seat/{seat.id}")
    assert 'id="winner_name"' in r.text
    assert 'type="text"' in r.text
