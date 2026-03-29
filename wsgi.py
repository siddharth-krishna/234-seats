"""PythonAnywhere WSGI entry point.

PythonAnywhere's server is WSGI-only. a2wsgi wraps the FastAPI (ASGI) app
so it runs under a standard WSGI server without any async worker.
"""

from a2wsgi import ASGIMiddleware

from app.main import app

application = ASGIMiddleware(app)
