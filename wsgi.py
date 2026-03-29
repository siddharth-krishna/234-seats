"""PythonAnywhere WSGI entry point.

PythonAnywhere's server is WSGI-only. a2wsgi wraps the FastAPI (ASGI) app
so it runs under a standard WSGI server without any async worker.

Environment variables are loaded from a .env file in this directory
(see README § Deployment for setup instructions).
"""

import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from a2wsgi import ASGIMiddleware  # noqa: E402

from app.main import app  # noqa: E402

application = ASGIMiddleware(app)
