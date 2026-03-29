"""Shared Jinja2Templates instance used by all route modules.

Defined here so the templates directory is resolved relative to this file,
not relative to the process working directory (which varies on PythonAnywhere).
"""

from pathlib import Path

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
