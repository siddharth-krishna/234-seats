"""Tests for admin party management routes."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.constituency import Constituency, Party
from app.models.election import Election
from app.models.user import User
from app.services.auth import create_session_token, hash_password


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


def test_parties_page_requires_admin(client: TestClient, regular_user: User, db: Session) -> None:
    db.commit()
    auth(client, regular_user)
    assert client.get("/admin/parties").status_code == 403


def test_parties_page_accessible_to_admin(client: TestClient, admin: User, db: Session) -> None:
    db.commit()
    auth(client, admin)
    assert client.get("/admin/parties").status_code == 200


# ── Create ─────────────────────────────────────────────────────────────────────


def test_create_party(client: TestClient, admin: User, db: Session) -> None:
    db.commit()
    auth(client, admin)
    r = client.post(
        "/admin/parties",
        data={"name": "DMK", "abbreviation": "DMK", "color_hex": "#e63946"},
    )
    assert r.status_code == 302
    party = db.query(Party).filter_by(name="DMK").first()
    assert party is not None
    assert party.color_hex == "#e63946"


def test_create_duplicate_party_returns_409(client: TestClient, admin: User, db: Session) -> None:
    db.add(Party(name="DMK", abbreviation="DMK"))
    db.commit()
    auth(client, admin)
    r = client.post(
        "/admin/parties", data={"name": "DMK", "abbreviation": "DMK", "color_hex": "#000"}
    )
    assert r.status_code == 409


# ── Update ─────────────────────────────────────────────────────────────────────


def test_update_party(client: TestClient, admin: User, db: Session) -> None:
    party = Party(name="DMK", abbreviation="DMK", color_hex="#aaaaaa")
    db.add(party)
    db.commit()
    auth(client, admin)
    client.post(
        f"/admin/parties/{party.id}",
        data={"name": "DMK", "abbreviation": "DMK", "color_hex": "#e63946"},
    )
    db.refresh(party)
    assert party.color_hex == "#e63946"


def test_update_party_name_and_abbreviation(client: TestClient, admin: User, db: Session) -> None:
    party = Party(name="Old Name", abbreviation="OLD")
    db.add(party)
    db.commit()
    auth(client, admin)
    client.post(
        f"/admin/parties/{party.id}",
        data={"name": "New Name", "abbreviation": "NEW", "color_hex": "#cccccc"},
    )
    db.refresh(party)
    assert party.name == "New Name"
    assert party.abbreviation == "NEW"


def test_update_nonexistent_party_returns_404(client: TestClient, admin: User, db: Session) -> None:
    db.commit()
    auth(client, admin)
    assert (
        client.post(
            "/admin/parties/9999",
            data={"name": "X", "abbreviation": "X", "color_hex": "#000"},
        ).status_code
        == 404
    )


# ── Delete ─────────────────────────────────────────────────────────────────────


def test_delete_party(client: TestClient, admin: User, db: Session) -> None:
    party = Party(name="DMK", abbreviation="DMK")
    db.add(party)
    db.commit()
    auth(client, admin)
    r = client.post(f"/admin/parties/{party.id}/delete")
    assert r.status_code == 302
    assert db.get(Party, party.id) is None


def test_delete_party_nulls_constituency_fk(client: TestClient, admin: User, db: Session) -> None:
    """Deleting a party removes the FK reference from constituencies."""
    party = Party(name="DMK", abbreviation="DMK")
    election = Election(name="TN 2026", year=2026, active=True)
    db.add_all([party, election])
    db.flush()
    seat = Constituency(
        election_id=election.id,
        number=1,
        name="Seat A",
        district="D",
        current_party_id=party.id,
    )
    db.add(seat)
    db.commit()
    auth(client, admin)
    client.post(f"/admin/parties/{party.id}/delete")
    db.refresh(seat)
    assert seat.current_party_id is None


def test_delete_nonexistent_party_returns_404(client: TestClient, admin: User, db: Session) -> None:
    db.commit()
    auth(client, admin)
    assert client.post("/admin/parties/9999/delete").status_code == 404
