# 234 Seats

A web app for predicting Tamil Nadu legislative assembly election results and comparing predictions with friends. Built for the April–May 2026 elections — 234 constituencies, one winner per seat.

Users submit a predicted winner, vote share, and comment for each constituency. After results are declared, a leaderboard ranks everyone by accuracy (correct seats, vote-share MAE/RMSE). Hosted on PythonAnywhere.

## Getting Started

**Prerequisites:** Python 3.12+, [`just`](https://github.com/casey/just)

```bash
git clone <repo-url>
cd 234-seats

# Create a virtual environment and install all dependencies
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# Install pre-commit hooks
just setup

# Configure environment
cp .env.example .env             # edit SECRET_KEY at minimum

# Set up the database
just migrate                     # create tables
just seed                        # load sample constituency data

# Start the dev server
just dev                         # http://localhost:8000

# Create a user to log in with
python scripts/create_users.py alice mypassword
python scripts/create_users.py admin mypassword --admin
```

Other useful commands:

```bash
just test      # run the test suite
just lint      # ruff check + format check
just fix       # auto-fix lint issues
```

## Deployment (PythonAnywhere)

PythonAnywhere supports FastAPI natively via their ASGI hosting (uvicorn over a
unix socket). Do **not** use the "Web" tab — use the `pa` CLI tool instead.

### One-time setup

1. Open a **Bash console** on PythonAnywhere and clone the repo:
   ```bash
   git clone <repo-url> ~/234-seats
   ```

2. Create a virtualenv and install dependencies:
   ```bash
   mkvirtualenv --python=python3.12 234-seats
   pip install -r ~/234-seats/requirements.txt
   ```

3. Create a `.env` file with your secrets (never commit this):
   ```bash
   cat > ~/234-seats/.env <<'EOF'
   SECRET_KEY=<long random string>
   DEBUG=False
   DATABASE_URL=sqlite:////home/<you>/234-seats/db.sqlite3
   EOF
   ```

4. So that `alembic` and scripts pick up those variables in the Bash console,
   source the `.env` file from your virtualenv's postactivate script:
   ```bash
   echo 'set -a; source ~/234-seats/.env; set +a' >> ~/.virtualenvs/234-seats/bin/postactivate
   workon 234-seats
   ```

5. Run migrations:
   ```bash
   cd ~/234-seats && alembic upgrade head
   ```

6. Install the `pa` CLI and create the ASGI web app:
   ```bash
   pip install pythonanywhere
   pa website create \
     --domain <you>.pythonanywhere.com \
     --command '/home/<you>/.virtualenvs/234-seats/bin/uvicorn --app-dir /home/<you>/234-seats --uds ${DOMAIN_SOCKET} app.main:app'
   ```

App is live at `<you>.pythonanywhere.com`.

### Redeploying after changes

Set these in your PythonAnywhere `~/.bashrc`:

```bash
export PA_DOMAIN=<you>.pythonanywhere.com
```

Then each deploy is one command:

```bash
bash ~/234-seats/scripts/pa_deploy.sh
```

This pulls the latest code, installs any new dependencies, runs migrations, and reloads the web app.

## Features

- Session-based login/logout (admin-created accounts, no self-registration)
- Constituency pages with prediction form (winner, vote share %, comment)
- Predictions from other users are hidden until you submit your own
- Leaderboard: correct seats, vote-share deviation (MAE, RMSE), sortable by column
- Admin: open/close predictions per seat, enter final results, publish writeups
- All election data scoped to an election object — reusable for future elections

## Wishlist

- Home page map of all 234 constituencies, colour-coded by prediction status; clickable
- Links to Harsh's blog posts and per-seat analysis
- Edit your prediction after submission (before predictions close)
- Scrape live results from ECI during results day
- Graph of leaderboard standings over time
- Export predictions and results as CSV/spreadsheet
- User badges and titles based on accuracy
- Archive a completed election; start fresh for the next one

## Original Prompt

- Home page shows a map of all the constituencies, a subset of which are clickable, and a table of users and overall metrics
    - clicking on a constituency takes you to the constituency page
    - links to Harsh’s blogs and analysis of the election overall
- The overall metrics table: 
    - table of users with columns: num predictions, correct seats so far, deviation in vote share (max, MAE, RMSE), 
    - Can sort by any column
- Constituency page:
    - Details: name, district, population, current MLA and party
    - A short writeup explaining the history and current context of the fight for this seat
    - User form to submit predictions (winner from dropdown, vote share % of winner, text prediction/comment for that seat)
    - After submission, can see a predictions table on this seat: each user’s predicted winner, vote share, comments
    - Can only see others’ predictions once you’ve submitted yours
    - After election results are out, the prediction table also has the actual winner and vote share
    - Stretch: Edit submission later?
- Managing the website:
    - To start with, many of these things can be hardcoded in the repo / edited manually using some utility scripts -- they don't need a web interface
    - Admin selects a set of seats that are open to predictions, and publish writeup for each, past X results
    - Register users?
        - Start with: admin makes usernames and passwords and sends to our group
    - Results:
        - Admin can enter final results manually
        - Stretch goal: periodically scrape live results from ECI and update winners-so-far
        - Stretch: graph of standings over time
- Stretch: Export results, predictions as CSV/spreadsheet
- Stretch: labels/badges/titles for each user based on wins / other honorable mentions
- After elections: add functionality to archive this election and use website again for a new one. This means the architecture of the website / database should be designed so that everything is tied to a particular election, so that it can be reused for the next election.

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Jinja2 templates + HTMX |
| Styling | Tailwind CSS (CDN) |
| Database | SQLite via SQLAlchemy 2 + Alembic |
| Auth | itsdangerous signed cookies + bcrypt |
| Hosting | PythonAnywhere |
| Tooling | ruff, ty, pytest, pre-commit, just |

See [`PLAN.md`](PLAN.md) for full architecture and implementation roadmap.
