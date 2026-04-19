"""Tests for admin routes."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.constituency import Constituency
from app.models.election import Election
from app.models.result import Result
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
        election_id=election.id, number=1, name="Seat A", district="D", predictions_open=False
    )
    db.add(c)
    db.flush()
    return c


@pytest.fixture()
def admin(db: Session) -> User:
    u = User(username="admin", hashed_password=hash_password("pass"), is_admin=True)
    db.add(u)
    db.flush()
    return u


@pytest.fixture()
def regular_user(db: Session) -> User:
    u = User(username="alice", hashed_password=hash_password("pass"), is_admin=False)
    db.add(u)
    db.flush()
    return u


def auth(client: TestClient, user: User) -> TestClient:
    client.cookies.set("session", create_session_token(user.id))
    return client


# ── Access control ─────────────────────────────────────────────────────────────


def test_admin_dashboard_requires_admin(
    client: TestClient, regular_user: User, election: Election, db: Session
) -> None:
    """Regular users get 403 on admin routes."""
    db.commit()
    auth(client, regular_user)
    assert client.get("/admin").status_code == 403


def test_admin_dashboard_unauthenticated_redirects(client: TestClient, db: Session) -> None:
    """Unauthenticated requests redirect to login."""
    db.commit()
    r = client.get("/admin")
    assert r.status_code == 302
    assert "/login" in r.headers["location"]


def test_admin_dashboard_accessible_to_admin(
    client: TestClient, admin: User, election: Election, db: Session
) -> None:
    """Admin users can access the dashboard."""
    db.commit()
    auth(client, admin)
    assert client.get("/admin").status_code == 200


# ── Open / close predictions ───────────────────────────────────────────────────


def test_open_predictions(client: TestClient, admin: User, seat: Constituency, db: Session) -> None:
    """Admin can open predictions for a seat."""
    db.commit()
    auth(client, admin)
    r = client.post(f"/admin/seat/{seat.id}/predictions/open")
    assert r.status_code == 302
    db.refresh(seat)
    assert seat.predictions_open is True


def test_close_predictions(
    client: TestClient, admin: User, seat: Constituency, db: Session
) -> None:
    """Admin can close predictions for a seat."""
    seat.predictions_open = True
    db.commit()
    auth(client, admin)
    r = client.post(f"/admin/seat/{seat.id}/predictions/close")
    assert r.status_code == 302
    db.refresh(seat)
    assert seat.predictions_open is False


def test_open_predictions_forbidden_for_regular_user(
    client: TestClient, regular_user: User, seat: Constituency, db: Session
) -> None:
    """Regular users cannot open predictions."""
    db.commit()
    auth(client, regular_user)
    assert client.post(f"/admin/seat/{seat.id}/predictions/open").status_code == 403


# ── Result entry ───────────────────────────────────────────────────────────────


def test_enter_result_creates_record(
    client: TestClient, admin: User, seat: Constituency, db: Session
) -> None:
    """Admin can enter a result for a seat."""
    db.commit()
    auth(client, admin)
    r = client.post(
        f"/admin/seat/{seat.id}/result",
        data={"winner_name": "The Winner", "winner_party": "DMK", "winner_vote_share": "48.5"},
    )
    assert r.status_code == 302
    result = db.query(Result).filter_by(constituency_id=seat.id).first()
    assert result is not None
    assert result.winner_name == "The Winner"
    assert result.winner_party == "DMK"
    assert result.winner_vote_share == pytest.approx(48.5)


def test_enter_result_updates_existing(
    client: TestClient, admin: User, seat: Constituency, db: Session
) -> None:
    """Entering a result twice updates the existing record."""
    db.add(Result(constituency_id=seat.id, winner_name="Old", winner_party="AIADMK"))
    db.commit()
    auth(client, admin)
    client.post(
        f"/admin/seat/{seat.id}/result",
        data={"winner_name": "New Winner", "winner_party": "DMK", "winner_vote_share": ""},
    )
    results = db.query(Result).filter_by(constituency_id=seat.id).all()
    assert len(results) == 1
    assert results[0].winner_name == "New Winner"
    assert results[0].winner_vote_share is None


def test_enter_result_forbidden_for_regular_user(
    client: TestClient, regular_user: User, seat: Constituency, db: Session
) -> None:
    """Regular users cannot enter results."""
    db.commit()
    auth(client, regular_user)
    r = client.post(
        f"/admin/seat/{seat.id}/result",
        data={"winner_name": "X", "winner_party": "Y", "winner_vote_share": ""},
    )
    assert r.status_code == 403


# ── Writeup ────────────────────────────────────────────────────────────────────


def test_save_writeup(client: TestClient, admin: User, seat: Constituency, db: Session) -> None:
    """Admin can save a writeup for a seat."""
    db.commit()
    auth(client, admin)
    client.post(
        f"/admin/seat/{seat.id}/writeup",
        data={"writeup": "Some context here.", "image_url": "https://example.com/seat.jpg"},
    )
    db.refresh(seat)
    assert seat.writeup == "Some context here."
    assert seat.image_url == "https://example.com/seat.jpg"


def test_save_empty_writeup_stores_none(
    client: TestClient, admin: User, seat: Constituency, db: Session
) -> None:
    """Saving an empty writeup stores None."""
    seat.writeup = "Old writeup"
    seat.image_url = "https://example.com/old.jpg"
    db.commit()
    auth(client, admin)
    client.post(f"/admin/seat/{seat.id}/writeup", data={"writeup": "   ", "image_url": "   "})
    db.refresh(seat)
    assert seat.writeup is None
    assert seat.image_url is None
