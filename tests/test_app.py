"""Smoke test — verifies the app factory works."""

from fastapi.testclient import TestClient

from app.main import app


def test_app_created() -> None:
    """The FastAPI app should be created without errors."""
    client = TestClient(app)
    assert client is not None


def test_openapi_schema() -> None:
    """The OpenAPI schema endpoint should return 200."""
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
