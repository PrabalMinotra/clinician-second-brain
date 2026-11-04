#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
(cd frontend && npm ci && npm run check && npm run build)
.venv/bin/python backend/manage.py migrate --noinput
.venv/bin/python backend/manage.py seed_demo
if [[ "$(uname)" == "Darwin" ]]; then bash scripts/build-ocr.sh; fi
printf 'Setup complete. Run bash scripts/start.sh. Credentials: .runtime/demo-login.txt\n'
