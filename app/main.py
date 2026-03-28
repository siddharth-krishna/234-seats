"""FastAPI application factory."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routes import auth as auth_router

_STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title="234 Seats",
        description="Election prediction webapp for Tamil Nadu 2026 assembly elections.",
        version="0.1.0",
    )

    # Expose the debug flag on app.state so routes can read it
    application.state.debug = settings.debug

    # Static files (CSS overrides, images, map SVG)
    application.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    # Routers
    application.include_router(auth_router.router)

    return application


app = create_app()
