"""Tests for authentication: services, dependencies, and login/logout routes."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.dependencies import COOKIE_NAME
from app.models.user import User
from app.services.auth import (
    create_session_token,
    decode_session_token,
    hash_password,
    verify_password,
)

# ── Service-layer unit tests ──────────────────────────────────────────────────


def test_hash_and_verify_password() -> None:
    """A password round-trips through hash and verify correctly."""
    hashed = hash_password("hunter2")
    assert verify_password("hunter2", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_session_token_roundtrip() -> None:
    """A session token encodes and decodes the user id."""
    token = create_session_token(42)
    assert decode_session_token(token) == 42


def test_session_token_tampered_returns_none() -> None:
    """A tampered token is rejected."""
    token = create_session_token(1)
    bad_token = token[:-4] + "xxxx"
    assert decode_session_token(bad_token) is None


def test_session_token_garbage_returns_none() -> None:
    """Garbage input returns None instead of raising."""
    assert decode_session_token("not-a-token") is None


# ── Route tests ───────────────────────────────────────────────────────────────


@pytest.fixture()
def user(db: Session) -> User:
    """A regular user in the test database."""
    u = User(username="alice", hashed_password=hash_password("pass123"))
    db.add(u)
    db.commit()
    return u


@pytest.fixture()
def admin_user(db: Session) -> User:
    """An admin user in the test database."""
    u = User(username="admin", hashed_password=hash_password("adminpass"), is_admin=True)
    db.add(u)
    db.commit()
    return u


def test_login_page_renders(client: TestClient) -> None:
    """GET /login returns 200."""
    response = client.get("/login")
    assert response.status_code == 200
    assert "Log in" in response.text


def test_login_success_redirects_and_sets_cookie(client: TestClient, user: User) -> None:
    """Valid credentials redirect to / and set a session cookie."""
    response = client.post("/login", data={"username": "alice", "password": "pass123"})
    assert response.status_code == 302
    assert response.headers["location"] == "/"
    assert COOKIE_NAME in response.cookies


def test_login_wrong_password(client: TestClient, user: User) -> None:
    """Wrong password returns 401 and shows an error message."""
    response = client.post("/login", data={"username": "alice", "password": "wrong"})
    assert response.status_code == 401
    assert "Invalid username or password" in response.text


def test_login_unknown_user(client: TestClient) -> None:
    """Unknown username returns 401."""
    response = client.post("/login", data={"username": "nobody", "password": "x"})
    assert response.status_code == 401


def test_logout_clears_cookie(client: TestClient, user: User) -> None:
    """POST /logout redirects to /login and deletes the session cookie."""
    # Log in first to get a cookie
    client.post("/login", data={"username": "alice", "password": "pass123"})
    response = client.post("/logout")
    assert response.status_code == 302
    assert response.headers["location"] == "/login"
    # Cookie should be cleared (empty value or absent)
    assert client.cookies.get(COOKIE_NAME) is None


def test_login_redirects_when_already_logged_in(client: TestClient, user: User) -> None:
    """GET /login redirects to / if already authenticated."""
    client.post("/login", data={"username": "alice", "password": "pass123"})
    # follow_redirects=False, so manually follow the login redirect first
    token = create_session_token(user.id)
    client.cookies.set(COOKIE_NAME, token)
    response = client.get("/login")
    assert response.status_code == 302
    assert response.headers["location"] == "/"
