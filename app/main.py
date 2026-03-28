"""FastAPI application factory."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routes import auth as auth_router
from app.routes import home as home_router

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

    # Redirect unauthenticated browser requests to the login page
    @application.exception_handler(401)
    async def _on_401(_request: Request, _exc: HTTPException) -> RedirectResponse:
        return RedirectResponse(url="/login")

    # Routers
    application.include_router(auth_router.router)
    application.include_router(home_router.router)

    return application


app = create_app()
