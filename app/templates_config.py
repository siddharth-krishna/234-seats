"""Shared Jinja2Templates instance used by all route modules.

Defined here so the templates directory is resolved relative to this file,
not relative to the process working directory (which varies on PythonAnywhere).
"""

from pathlib import Path

from fastapi.templating import Jinja2Templates
from markdown import markdown
from markupsafe import Markup

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def render_markdown(text: str | None) -> Markup:
    """Render markdown text into safe template output."""
    if not text:
        return Markup("")
    html = markdown(text, extensions=["extra", "nl2br", "sane_lists"])
    return Markup(html)


templates.env.filters["markdown"] = render_markdown
