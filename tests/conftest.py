"""Shared pytest fixtures."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models as _models  # noqa: F401  # ensures all models are registered with Base
from app.database import Base, get_db
from app.main import app


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """In-memory SQLite session for each test, with all tables created.

    StaticPool forces SQLAlchemy to reuse a single connection, so the
    in-memory database is shared across threads (necessary when FastAPI
    runs route handlers in worker threads via anyio).
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def client(db: Session) -> Generator[TestClient, None, None]:
    """TestClient with the real app, DB replaced by the in-memory fixture."""

    def override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, follow_redirects=False) as c:
        yield c
    app.dependency_overrides.clear()
