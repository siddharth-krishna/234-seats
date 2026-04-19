# AI Agent Instructions — 234 Seats

## Project

A Python/FastAPI election-prediction webapp for Tamil Nadu 2026 assembly elections.
~10–20 users submit winner/vote-share predictions per constituency; a leaderboard
tracks accuracy after results. Hosted on PythonAnywhere with SQLite.

See `PLAN.md` for full architecture, data model, and phased roadmap.

## Stack

- **Backend:** FastAPI + Jinja2 templates + HTMX (no JS build toolchain)
- **Database:** SQLite via SQLAlchemy 2 ORM + Alembic migrations
- **Auth:** itsdangerous signed session cookies + passlib/bcrypt
- **Tooling:** ruff (lint + format), ty (type checking), pytest, pre-commit, just

## Environment Setup

**Always activate the virtual environment before running any Python commands:**

```bash
source .venv/bin/activate
```

If the venv doesn't exist yet:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pre-commit install
```

All commands below assume the venv is active.

## Database

The SQLite database file is **`234seats.db`** in the project root (set by
`DATABASE_URL=sqlite:///./234seats.db` in `.env` / `.env.example`).

To reset the local dev database from scratch:
```bash
just reset-db   # rm 234seats.db && alembic upgrade head
```

## Running Tests

Run the full test suite with:

```bash
python -m pytest tests/          # preferred — explicit, works from any cwd
# or
just test                        # shorthand via justfile
```

Tests use an in-memory SQLite database (configured in `tests/conftest.py`) and
`httpx.AsyncClient` against the FastAPI app. They are fast (~15s for 70 tests)
and require no running server or external services.

Useful flags:

```bash
python -m pytest tests/ -v             # verbose: show each test name
python -m pytest tests/ -x             # stop on first failure
python -m pytest tests/test_auth.py    # run a single file
python -m pytest -k "test_login"       # run tests matching a pattern
```

**Always run tests after making code changes.** All 70 tests must pass before committing.
**Always run pre-commit after making code changes and before finishing the task.**

## Other Dev Commands

```bash
just dev      # start dev server with auto-reload at http://localhost:8000
just lint     # ruff check + ruff format --check + ty check
just fix      # auto-fix lint/format issues (ruff only)
just precommit # run all configured pre-commit hooks
just migrate  # apply pending Alembic migrations
just seed     # seed constituency data from scripts/seed_constituencies.py
just create-user alice pw123 --admin   # create a user account
```

## Scraping and Web Fetching

- **Always save fetched pages to a temp file** before parsing — never re-download
  the same page multiple times in a session:
  ```bash
  curl -s "https://example.com/page" -o /tmp/page.html
  # then read from /tmp/page.html for all subsequent work
  ```
- **Use BeautifulSoup** (`from bs4 import BeautifulSoup`) to parse HTML — never
  use `re` to extract content from HTML. BeautifulSoup is in `requirements-dev.txt`
  and always available in the venv.

## Regenerating the SVG Map

The TN constituency SVG at `app/static/tn_map.svg` is committed. If it needs to
be regenerated (e.g. after a delimitation change):

```bash
python scripts/generate_tn_map.py
```

This downloads the India_AC shapefile from datameet/maps and re-exports the SVG.
Requires `pyshp` (in `requirements-dev.txt`).

## Coding Conventions

- **Type hints on all public functions and class attributes.** `ty check` must pass.
- **Ruff** enforces style — run `just fix` to auto-correct, `just lint` to check.
- **Google-style docstrings** on all public functions and classes.
- **No logic in route handlers.** Handlers call service functions; all business logic
  lives in `app/services/`.
- **One Alembic migration per schema change** — never modify existing migrations.
- **Secrets via environment variables only.** Never hardcode secrets or commit `.env`.
- **No raw SQL** outside of explicitly marked query helpers.
- **Templates use Tailwind CSS (CDN) and HTMX.** No JS build step. Keep JS minimal
  and inline in templates; only use `app/static/` for assets (SVG map, images).

## What NOT to do

- Do not add features or refactor code beyond what is explicitly requested.
- Do not add error handling for impossible cases or add unnecessary fallbacks.
- Do not create new files unless absolutely necessary — prefer editing existing ones.
- Do not add docstrings or comments to code you did not change.
- Do not skip or bypass pre-commit hooks (`--no-verify`).
- Do not introduce `psycopg2`, `asyncpg`, or any PostgreSQL driver — this project
  uses SQLite.

## Project Structure

```
app/
  main.py          # FastAPI app factory; error handlers (401/403/404/500)
  config.py        # pydantic-settings: DATABASE_URL, SECRET_KEY, DEBUG
  database.py      # engine, SessionLocal, Base, get_db dependency
  models/          # SQLAlchemy ORM models
  routes/          # FastAPI routers (one file per feature area)
  services/        # Business logic (auth, scoring, results)
  templates/       # Jinja2 HTML templates (base.html, home.html, …)
  static/          # tn_map.svg (234-constituency SVG map), images
migrations/        # Alembic migration scripts
scripts/           # Admin CLI scripts (not web routes)
  generate_tn_map.py   # regenerate app/static/tn_map.svg from shapefile
tests/             # pytest tests
wsgi.py            # PythonAnywhere ASGI entry point
```
