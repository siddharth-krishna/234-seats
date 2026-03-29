#!/usr/bin/env bash
# Deploy script for PythonAnywhere.
# Run from the PythonAnywhere Bash console:
#
#   bash ~/234-seats/scripts/pa_deploy.sh
#
# Required environment variables (set in ~/.bashrc on PythonAnywhere):
#   PA_DOMAIN  — e.g. 234seats.pythonanywhere.com

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
pa website reload --domain "${PA_DOMAIN}"

echo "==> Deploy complete: https://${PA_DOMAIN}"
