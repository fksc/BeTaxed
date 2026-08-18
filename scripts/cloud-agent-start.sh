#!/usr/bin/env bash
# Per-boot service reconciliation for the BeTaxed Cloud Agent environment.
# Starts PostgreSQL 18 and Redis 8, ensures the app role/database exist, and
# applies Alembic migrations. Idempotent: tolerates already-running services.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PG_VER=18
PG_BIN="/usr/lib/postgresql/${PG_VER}/bin"
DB_NAME="${POSTGRES_DB:-betaxed}"
DB_USER="${POSTGRES_USER:-betaxed}"
DB_PASS="${POSTGRES_PASSWORD:-betaxed_dev}"
REDIS_PORT="${REDIS_PORT:-6380}"

echo "[start] Ensuring PostgreSQL ${PG_VER} is running"
if ! sudo pg_ctlcluster "${PG_VER}" main status >/dev/null 2>&1; then
  sudo pg_ctlcluster "${PG_VER}" main start
fi
for _ in $(seq 1 30); do
  if "${PG_BIN}/pg_isready" -h 127.0.0.1 -p 5432 >/dev/null 2>&1; then break; fi
  sleep 1
done
"${PG_BIN}/pg_isready" -h 127.0.0.1 -p 5432

echo "[start] Ensuring role '${DB_USER}' and database '${DB_NAME}'"
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1; then
  sudo -u postgres psql -v ON_ERROR_STOP=1 -c "CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASS}'"
fi
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1; then
  sudo -u postgres createdb -O "${DB_USER}" "${DB_NAME}"
fi

echo "[start] Ensuring Redis on port ${REDIS_PORT}"
if ! redis-cli -p "${REDIS_PORT}" ping >/dev/null 2>&1; then
  redis-server --port "${REDIS_PORT}" --daemonize yes --save '' --appendonly no
fi

echo "[start] Applying Alembic migrations"
cd "$REPO_ROOT/backend"
if [ -x .venv/bin/alembic ]; then
  # No revisions exist yet; this validates DB connectivity and is a no-op then.
  .venv/bin/alembic upgrade head
fi

echo "[start] Ready"
