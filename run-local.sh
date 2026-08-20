#!/usr/bin/env bash
# Run the backend locally.
# Config (DATABASE_URI, port, debug mode) comes from .env in this directory.
#
# Usage:
#   ./run-local.sh              # auto-reload on code changes (from FLASK_DEBUG=1 in .env)
#   ./run-local.sh --reload     # force auto-reload on
#   ./run-local.sh --no-reload  # disable auto-reload
#   ./run-local.sh --port 5002  # any extra flags are passed to `flask run`
set -e
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "Missing .env file. Create one with:"
  echo '  DATABASE_URI=postgresql://postgres:postgres@localhost:5432/lemko_memory_book'
  echo '  FLASK_APP=app'
  echo '  FLASK_DEBUG=1'
  echo '  FLASK_RUN_PORT=5001'
  exit 1
fi

exec ./venv/bin/flask run "$@"
