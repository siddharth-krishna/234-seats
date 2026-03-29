"""FastAPI application factory."""

from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routes import admin as admin_router
from app.routes import auth as auth_router
from app.routes import constituency as constituency_router
from app.routes import home as home_router
from app.templates_config import templates

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
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    @application.exception_handler(403)
    async def _on_403(request: Request, _exc: HTTPException) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "current_user": None,
                "status_code": 403,
                "title": "Access denied",
                "detail": "You don't have permission to view this page.",
            },
            status_code=403,
        )

    @application.exception_handler(404)
    async def _on_404(request: Request, _exc: HTTPException) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "current_user": None,
                "status_code": 404,
                "title": "Page not found",
                "detail": "The page you're looking for doesn't exist or has been moved.",
            },
            status_code=404,
        )

    @application.exception_handler(500)
    async def _on_500(request: Request, _exc: Exception) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "current_user": None,
                "status_code": 500,
                "title": "Something went wrong",
                "detail": "An unexpected error occurred. Please try again later.",
            },
            status_code=500,
        )

    # Routers
    application.include_router(auth_router.router)
    application.include_router(home_router.router)
    application.include_router(constituency_router.router)
    application.include_router(admin_router.router)

    return application


app = create_app()
