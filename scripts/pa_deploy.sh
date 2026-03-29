#!/usr/bin/env bash
# Deploy script for PythonAnywhere.
# Run from the PythonAnywhere Bash console:
#
#   bash ~/234-seats/scripts/pa_deploy.sh
#
# Required environment variables (set in your PA bash profile or .env):
#   PA_USERNAME   — your PythonAnywhere username
#   PA_DOMAIN     — web app domain, e.g. username.pythonanywhere.com
#   PA_API_TOKEN  — API token from pythonanywhere.com/user/<you>/account/#api_token

set -euo pipefail

REPO_DIR="$HOME/234-seats"
VENV="$HOME/.virtualenvs/234-seats"

echo "==> Pulling latest code"
cd "$REPO_DIR"
git pull

echo "==> Installing/updating dependencies"
source "$VENV/bin/activate"
pip install -q -r requirements.txt

echo "==> Running migrations"
alembic upgrade head

echo "==> Reloading web app"
curl -s -X POST \
  "https://www.pythonanywhere.com/api/v0/user/${PA_USERNAME}/webapps/${PA_DOMAIN}/reload/" \
  -H "Authorization: Token ${PA_API_TOKEN}"

echo ""
echo "==> Deploy complete: https://${PA_DOMAIN}"
