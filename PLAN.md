# 234 Seats — Implementation Plan

## Overview

A lightweight election-prediction webapp for ~10–20 friends to submit and compare
predictions on Tamil Nadu 2026 assembly election seats. Users predict the winner,
vote share, and leave a comment for each seat; a leaderboard tracks accuracy after
results are in.

---

## Architecture

```
┌─────────────────────────────────────────────┐
│                   Browser                   │
│  Jinja2 HTML + HTMX + Tailwind CSS (CDN)    │
└─────────────────┬───────────────────────────┘
                  │ HTTP
┌─────────────────▼───────────────────────────┐
│           FastAPI (Python)                  │
│  • HTML routes (Jinja2 templates)           │
│  • JSON API routes (/api/*)                 │
│  • Session-based auth (itsdangerous)        │
└─────────────────┬───────────────────────────┘
                  │ SQLAlchemy ORM
┌─────────────────▼───────────────────────────┐
│         SQLite (prod + dev)                  │
│  Alembic migrations                        │
└─────────────────────────────────────────────┘
```

### Why this stack?

| Choice | Reason |
|---|---|
| **FastAPI** | Python-native, async, auto-generated OpenAPI docs, fast to build |
| **Jinja2 + HTMX** | Server-rendered pages with sprinkles of interactivity — no JS build toolchain |
| **Tailwind CSS (CDN)** | Utility-first styling, zero config |
| **SQLAlchemy + Alembic** | Standard Python ORM + migrations; easy to swap SQLite↔PostgreSQL |
| **itsdangerous** | Signed session cookies; no JWT complexity for a small app |
| **SQLite** | Perfect for PythonAnywhere (no Postgres on free tier); fine for 20 users |

---

## Data Model (high-level)

```
Election
  id, name, year, description, active: bool

Constituency
  id, election_id, name, district, population
  current_mla, current_party
  writeup (text), predictions_open: bool

Party
  id, name, abbreviation, color_hex

Candidate         (actual candidates — added before/after results)
  id, constituency_id, party_id, name

User
  id, username, hashed_password, is_admin, created_at

Prediction
  id, user_id, constituency_id
  predicted_winner (candidate name / free text)
  predicted_vote_share (float)
  comment (text)
  submitted_at, updated_at

Result            (filled in after results are declared)
  id, constituency_id
  winner_candidate_id, winner_vote_share
  declared_at
```

---

## Tech Stack

| Layer | Library/Tool | Version |
|---|---|---|
| Python | — | 3.12+ |
| Web framework | `fastapi` | latest |
| ASGI server | `uvicorn[standard]` | latest |
| Templating | `jinja2` | latest |
| ORM | `sqlalchemy` | 2.x |
| Migrations | `alembic` | latest |
| Auth/sessions | `itsdangerous` | latest |
| Password hashing | `passlib[bcrypt]` | latest |
| Forms | `python-multipart` | latest |
| DB driver (prod) | `asyncpg` or `psycopg2` | latest |
| Config | `pydantic-settings` | latest |
| Linting | `ruff` | latest |
| Formatting | `ruff format` | latest |
| Type checking | `ty` (Astral) | latest |
| Testing | `pytest` + `httpx` | latest |
| Test DB | SQLite (in-memory) | — |
| Pre-commit hooks | `pre-commit` | latest |
| Task runner | `just` (justfile) | latest |

---

## Project Structure

```
234-seats/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app factory
│   ├── config.py            # pydantic-settings config
│   ├── database.py          # engine, session, Base
│   ├── models/              # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── election.py
│   │   ├── constituency.py
│   │   ├── user.py
│   │   ├── prediction.py
│   │   └── result.py
│   ├── routes/              # FastAPI routers
│   │   ├── __init__.py
│   │   ├── auth.py          # login, logout
│   │   ├── home.py          # leaderboard, map
│   │   ├── constituency.py  # seat detail + predictions
│   │   └── admin.py         # admin-only utilities
│   ├── services/            # business logic
│   │   ├── auth.py
│   │   ├── scoring.py       # accuracy metrics
│   │   └── results.py
│   ├── templates/           # Jinja2 HTML templates
│   │   ├── base.html
│   │   ├── home.html
│   │   ├── constituency.html
│   │   ├── login.html
│   │   └── admin/
│   └── static/              # CSS overrides, images, map SVG
├── migrations/              # Alembic migrations
├── scripts/                 # Admin CLI scripts
│   ├── seed_constituencies.py
│   ├── import_results.py
│   └── create_users.py
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_predictions.py
│   └── test_scoring.py
├── .env.example
├── .pre-commit-config.yaml
├── justfile
├── pyproject.toml           # ruff, ty, pytest config
├── requirements.txt         # pinned prod deps
├── requirements-dev.txt     # dev deps (pytest, ruff, ty, pre-commit)
├── wsgi.py                  # PythonAnywhere WSGI entry point
├── AGENTS.md                # AI assistant instructions
├── PLAN.md                  # this file
└── README.md
```

---

## Roadmap

Each phase is self-contained and leaves the app in a working, deployable state.

---

### Phase 0 — Project Scaffolding & Tooling

*Goal: working repo with all developer tooling configured before a line of app code is written.*

- [ ] `pyproject.toml` with `ruff` (lint + format), `ty`, `pytest` config
- [ ] `.pre-commit-config.yaml`: ruff, ty, trailing whitespace, end-of-file-fixer
- [ ] `justfile` with recipes: `just dev`, `just test`, `just lint`, `just migrate`, `just seed`
- [ ] `AGENTS.md` with project context, coding conventions, and instructions for AI assistants
- [ ] `.env.example` documenting all required environment variables
- [ ] `requirements.txt` and `requirements-dev.txt` (or a single `pyproject.toml` with optional deps)
- [ ] GitHub Actions CI: lint + test on every push

**Test at this stage:** `just lint` and `just test` both pass on an empty test suite.

---

### Phase 1 — Database Models & Migrations

*Goal: define the full schema; be able to create and inspect the database locally.*

- [ ] `app/database.py`: SQLAlchemy engine factory, `get_db` dependency, `Base`
- [ ] `app/config.py`: `DATABASE_URL`, `SECRET_KEY`, `DEBUG` via pydantic-settings
- [ ] All SQLAlchemy models (Election, Constituency, Party, User, Prediction, Result)
- [ ] Alembic setup + initial migration
- [ ] `scripts/seed_constituencies.py`: load a CSV/JSON of the 234 TN constituencies
- [ ] Unit tests: model creation, relationship traversal (using SQLite in-memory)

**Test at this stage:** `just migrate` creates all tables; `just seed` populates constituencies.

---

### Phase 2 — Auth (Login/Logout)

*Goal: users can log in and out; admin flag distinguishes admins from regular users.*

- [ ] `app/models/user.py`: User model with hashed password
- [ ] `app/services/auth.py`: password hashing (bcrypt), session cookie signing
- [ ] `app/routes/auth.py`: `GET /login`, `POST /login`, `POST /logout`
- [ ] `app/templates/login.html`: minimal login form
- [ ] `scripts/create_users.py`: admin CLI to create/reset user accounts
- [ ] Auth middleware / dependency: `get_current_user`, `require_admin`
- [ ] Unit tests: login success/failure, session creation, protected route returns 401

**Test at this stage:** can log in/out; protected routes redirect to login.

---

### Phase 3 — Home Page & Leaderboard

*Goal: a working landing page showing the metrics table (even if all zeros initially).*

- [ ] `app/routes/home.py`: `GET /`
- [ ] `app/services/scoring.py`: compute per-user stats (num predictions, correct seats, vote-share MAE/RMSE)
- [ ] `app/templates/home.html`: sortable leaderboard table, list of open constituencies
- [ ] Static Tamil Nadu SVG map (placeholder; constituencies greyed out / highlighted based on status)
- [ ] Unit tests: scoring functions with known fixture data

**Test at this stage:** home page loads; leaderboard shows all users with zeroed stats.

---

### Phase 4 — Constituency Page & Predictions

*Goal: core feature — users can submit predictions and view others' after submitting.*

- [ ] `app/routes/constituency.py`:
  - `GET /seat/<id>` — show details + form (or predictions table if already submitted)
  - `POST /seat/<id>/predict` — submit or update prediction
- [ ] `app/templates/constituency.html`: seat info, prediction form, hidden-until-submitted table
- [ ] Business logic: prevent viewing others' predictions before submitting your own
- [ ] HTMX: submit form and reload predictions table without full page refresh
- [ ] Unit tests: prediction submission, duplicate prevention, visibility rules

**Test at this stage:** full end-to-end prediction flow works for a logged-in user.

---

### Phase 5 — Admin Utilities & Seat Management

*Goal: admin can manage the election cycle without touching the database directly.*

- [ ] `app/routes/admin.py`:
  - Open/close predictions for a seat
  - Enter final results for a seat
  - Publish/edit seat writeup
- [ ] `app/templates/admin/`: simple admin dashboard
- [ ] `scripts/import_results.py`: bulk-import results from CSV
- [ ] After results are entered: leaderboard shows actual accuracy metrics
- [ ] Unit tests: admin-only routes are rejected for regular users

**Test at this stage:** admin can manage the full election lifecycle end-to-end.

---

### Phase 6 — Deployment (PythonAnywhere)

*Goal: app is live on PythonAnywhere, accessible via custom domain (requires Hacker plan, ~$5/mo).*

- [ ] `wsgi.py` entry point for PythonAnywhere's WSGI server
- [ ] Configure PythonAnywhere web app: source dir, virtualenv path, WSGI file
- [ ] Upload/clone repo; create virtualenv and install `requirements.txt`
- [ ] `alembic upgrade head` from PythonAnywhere bash console
- [ ] Set environment variables via PythonAnywhere web UI (SECRET_KEY, DEBUG=False)
- [ ] HTTPS is automatic on pythonanywhere.com subdomain
- [ ] Custom domain setup (Hacker plan required for custom CNAME)
- [ ] Smoke tests against the live URL

**Test at this stage:** app is live at `<username>.pythonanywhere.com`; users can log in and submit predictions.

---

### Phase 7 — Map & Polish

*Goal: interactive SVG map on the home page; general UI polish.*

- [ ] Clickable SVG map of Tamil Nadu constituencies (color-coded by party/prediction status)
- [ ] Mobile-responsive layout
- [ ] Links to Harsh's blog/analysis per seat
- [ ] Sort-by-column on the leaderboard (HTMX or JS)
- [ ] Graceful error pages (404, 403, 500)

---

### Phase 8 — Stretch Goals (post-election)

- [ ] Edit predictions before deadline
- [ ] Graph of standings over time
- [ ] Live result scraping from ECI
- [ ] CSV export of predictions/results
- [ ] User badges/titles
- [ ] Archive this election; support multi-election use

---

## Coding Conventions

- **Type hints everywhere.** `ty --strict` must pass.
- **Ruff** for linting and formatting (replaces black, isort, flake8).
- **Docstrings** on all public functions and classes (Google style).
- **No logic in route handlers** — handlers call service functions; services contain logic.
- **One Alembic migration per schema change.**
- **Tests live next to the code they test** (in `tests/`); use `pytest` fixtures in `conftest.py`.
- **Secrets via environment variables only** — never commit `.env`.
- **AGENTS.md** documents project context, conventions, and "do not do" rules for AI assistants.

---

## AGENTS.md (to be created in Phase 0)

Will contain:
- Project purpose and architecture summary
- Coding conventions (above)
- Database model summary
- Do not: hardcode secrets, add unrequested features, break ty strict, use raw SQL outside of explicitly marked query files

---

## Hosting Options

For a hobby app with ~10–20 users and a Python backend + PostgreSQL, here are the
best free options. Prices and limits change — verify on each platform's pricing page
before committing.

---

### Option A — Fly.io (app + SQLite on persistent volume)
**Recommended: most capable genuinely-free tier**

| | |
|---|---|
| Free allowance | 3 shared-CPU VMs (256 MB RAM each), 3 GB persistent storage, 160 GB outbound/month |
| Sleep | Configurable — can stay always-on within free limits |
| Custom domain | Yes (free TLS) |
| Database | SQLite on a persistent volume (perfect for this scale), or self-managed Fly Postgres |
| Credit card | Required to sign up, but won't charge within free limits |

**Pros:** Always-on, real persistent disk, full Docker containers, excellent CLI (`flyctl`),
SQLite works perfectly — no Postgres to manage.

**Cons:** Steeper learning curve (Dockerfile + `fly.toml`); self-managed Postgres if you
want it; requires credit card.

**Notes to verify:** Current free CPU/RAM/storage allowances at fly.io/docs/about/pricing/

---

### Option B — Render (app) + Supabase (database)
**Runner-up: easiest setup, permanent free Postgres**

| | Render (app) | Supabase (DB) |
|---|---|---|
| Free tier | 512 MB RAM, 100 GB bandwidth | 500 MB Postgres storage, 5 GB bandwidth |
| Sleep | Spins down after 15 min inactivity (~30s cold start) | Pauses after 7 days inactivity (~30s wake) |
| Custom domain | Yes (free TLS) | N/A (DB endpoint) |
| Credit card | No | No |

**Pros:** No credit card needed on either; Supabase gives permanent free Postgres (unlike
Render's 90-day expiry); Render auto-deploys from GitHub with minimal config.

**Cons:** Cold start (~30s) on first visit after idle period; Render's own free Postgres
deletes after 90 days (hence pairing with Supabase); Supabase pauses after a week of no
activity.

**Notes to verify:** Render free tier at render.com/pricing; Supabase pause policy at
supabase.com/pricing.

---

### Option C — PythonAnywhere
**Simplest option: always-on, no containers, no credit card**

| | |
|---|---|
| Free tier | ~512 MB RAM, 512 MB storage, always-on web app |
| Sleep | None — stays up 24/7 |
| Custom domain | No (free tier: `yourusername.pythonanywhere.com` only) |
| Database | SQLite or MySQL (no Postgres on free tier) |
| Credit card | No |

**Pros:** Never sleeps, Python-native (upload code + configure WSGI), simplest possible deploy.

**Cons:** No custom domain (must pay ~$5/mo for Hacker plan); no PostgreSQL; outbound HTTP
is whitelist-limited; CPU quota is strict.

---

### Option D — Railway (Hobby plan, ~$0–5/month)
**Best developer experience; not truly free but near-free for quiet apps**

| | |
|---|---|
| Plan | Hobby ($5/month credit included — quiet apps may cost <$1/month) |
| Sleep | None — always running |
| Custom domain | Yes |
| Database | PostgreSQL plugin, persistent volumes |
| Credit card | Yes |

**Pros:** No cold starts, excellent DX, usage-based billing, one-click Postgres add-on.

**Cons:** Not free — requires Hobby plan at $5/mo (though included usage credit often covers it).

---

### Comparison Summary

| Platform | Always On | Free Postgres | Custom Domain | Credit Card | Difficulty |
|---|---|---|---|---|---|
| **Fly.io** | Yes (configurable) | Self-managed | Yes | Yes | Medium |
| **Render + Supabase** | No (15min sleep) | Yes (Supabase) | Yes | No | Easy |
| **PythonAnywhere** | Yes | No (MySQL) | Paid only | No | Easiest |
| **Railway** | Yes | Yes (plugin) | Yes | Yes | Easy |

### Recommendation

- **Best overall:** **Fly.io** — persistent SQLite, always-on, generous free limits, custom domain.
  Use `fly launch` from a Dockerfile; `fly volumes create` for persistent storage.
- **Easiest setup / no credit card:** **Render + Supabase** — acceptable cold starts for a
  low-traffic hobby site; free forever as long as you touch it every 7 days.
- **If you don't need a custom domain at all:** **PythonAnywhere** — literally upload files
  and it works.
