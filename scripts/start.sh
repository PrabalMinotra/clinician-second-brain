#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
exec .venv/bin/python backend/manage.py runserver 127.0.0.1:8000 --noreload
