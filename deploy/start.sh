#!/usr/bin/env bash
set -euo pipefail
umask 077
python backend/manage.py check --deploy --fail-level ERROR
python backend/manage.py migrate --noinput
python backend/manage.py seed_demo
exec gunicorn --chdir backend config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 1 --threads 4 --timeout 120 --error-logfile -
