"""FastAPI application factory."""

from fastapi import FastAPI


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title="234 Seats",
        description="Election prediction webapp for Tamil Nadu 2026 assembly elections.",
        version="0.1.0",
    )
    return application


app = create_app()
