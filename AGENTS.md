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

## Coding Conventions

- **Type hints on all public functions and class attributes.** `ty check` must pass.
- **Ruff** enforces style — run `just fix` to auto-correct, `just lint` to check.
- **Google-style docstrings** on all public functions and classes.
- **No logic in route handlers.** Handlers call service functions; all business logic
  lives in `app/services/`.
- **One Alembic migration per schema change** — never modify existing migrations.
- **Secrets via environment variables only.** Never hardcode secrets or commit `.env`.
- **No raw SQL** outside of explicitly marked query helpers.

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
  main.py          # FastAPI app factory
  config.py        # pydantic-settings: DATABASE_URL, SECRET_KEY, DEBUG
  database.py      # engine, SessionLocal, Base, get_db dependency
  models/          # SQLAlchemy ORM models
  routes/          # FastAPI routers (one file per feature area)
  services/        # Business logic (auth, scoring, results)
  templates/       # Jinja2 HTML templates
  static/          # CSS overrides, SVG map, images
migrations/        # Alembic migration scripts
scripts/           # Admin CLI scripts (not web routes)
tests/             # pytest tests
wsgi.py            # PythonAnywhere WSGI entry point
```

## Running locally

```bash
just setup    # install deps + pre-commit hooks
cp .env.example .env
just migrate  # create database tables
just seed     # populate constituencies
just dev      # start dev server at http://localhost:8000
just test     # run tests
just lint     # check code quality
```
