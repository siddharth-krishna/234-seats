# 234 Seats — task runner
# Install: https://github.com/casey/just

# List available recipes
default:
    @just --list

# ── Development ──────────────────────────────────────────────────────────────

# Run the dev server with auto-reload
dev:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# ── Code quality ─────────────────────────────────────────────────────────────

# Run all linters (ruff lint + format check + ty)
lint:
    ruff check .
    ruff format --check .
    ty check .

# Auto-fix lint issues and reformat
fix:
    ruff check --fix .
    ruff format .

# ── Tests ─────────────────────────────────────────────────────────────────────

# Run the test suite
test:
    pytest

# Run tests with verbose output
test-v:
    pytest -v

# ── Database ──────────────────────────────────────────────────────────────────

# Apply all pending Alembic migrations
migrate:
    alembic upgrade head

# Create a new Alembic migration (usage: just new-migration "add users table")
new-migration msg:
    alembic revision --autogenerate -m "{{msg}}"

# ── Data management ───────────────────────────────────────────────────────────

# Seed the database with constituency data
seed:
    python scripts/seed_constituencies.py

# Create a user (usage: just create-user username password [--admin])
create-user *args:
    python scripts/create_users.py {{args}}

# ── Setup ─────────────────────────────────────────────────────────────────────

# Install dev dependencies and pre-commit hooks
setup:
    pip install -r requirements-dev.txt
    pre-commit install
