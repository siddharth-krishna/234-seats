"""WSGI shim — not used in production.

Production deployment uses PythonAnywhere's native ASGI support (uvicorn
via the `pa` CLI). See README § Deployment for setup instructions.

This file is kept only as a fallback if WSGI is ever needed.
"""
