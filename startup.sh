#!/usr/bin/env bash
# Azure App Service startup command: `bash startup.sh`
# Applies pending DB migrations, then starts the web server.
set -u
cd "$(dirname "$0")"

echo "Running database migrations..."
if ! flask --app wsgi db upgrade; then
  # Don't take the site down over a failed migration; the previous schema still works.
  echo "WARNING: database migration failed; starting app on the existing schema." >&2
fi

exec gunicorn wsgi:app
