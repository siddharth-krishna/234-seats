"""Tests for theme toggling and favicon wiring."""

from fastapi.testclient import TestClient

from app.main import app


def test_theme_toggle_sets_dark_cookie_and_redirects() -> None:
    """Posting to /theme toggles to dark mode by default."""
    client = TestClient(app, follow_redirects=False)
    response = client.post("/theme", data={"next": "/login"})
    assert response.status_code == 302
    assert response.headers["location"] == "/login"
    assert response.cookies.get("theme") == "dark"


def test_theme_toggle_sets_light_cookie_when_current_is_dark() -> None:
    """Posting to /theme toggles dark mode back to light."""
    client = TestClient(app, follow_redirects=False)
    client.cookies.set("theme", "dark")
    response = client.post("/theme", data={"next": "/"})
    assert response.status_code == 302
    assert response.cookies.get("theme") == "light"
