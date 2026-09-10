#!/bin/sh
# Apply migrations before serving, so the schema the app expects is the schema
# that exists. Fails fast: if a migration cannot apply, the container must not
# come up pretending to be healthy.
set -e

echo "[entrypoint] applying database migrations"
alembic upgrade head

echo "[entrypoint] starting uvicorn"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 "$@"
