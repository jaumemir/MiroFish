#!/bin/sh
set -e

cd /app/backend
uv run python scripts/init_system.py

exec .venv/bin/gunicorn \
  --bind 0.0.0.0:5001 \
  --workers 1 \
  --threads 4 \
  --timeout 300 \
  --worker-class gthread \
  wsgi:application
