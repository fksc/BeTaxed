#!/usr/bin/env bash
# Wipe local Docker volumes (Postgres + Auth emulator), migrate, seed ops staff.
# Usage: from repo root: ./scripts/reset-local-dev.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="${ROOT}/backend/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Missing backend/.venv. Create it and pip install -r backend/requirements.txt" >&2
  exit 1
fi

echo "Stopping stack and deleting named volumes (Postgres + Auth emulator)…"
docker compose down -v

echo "Starting postgres, redis, firebase-auth…"
docker compose up -d postgres redis firebase-auth

echo "Waiting for Postgres…"
for _ in $(seq 1 40); do
  if docker exec betaxed-postgres pg_isready -U betaxed -d betaxed >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
docker exec betaxed-postgres pg_isready -U betaxed -d betaxed >/dev/null

echo "Waiting for Auth emulator…"
for _ in $(seq 1 40); do
  if curl -sf http://127.0.0.1:9099/ >/dev/null; then
    break
  fi
  sleep 1
done
curl -sf http://127.0.0.1:9099/ >/dev/null

if [[ -d "${ROOT}/backend/.local_storage" ]]; then
  rm -rf "${ROOT}/backend/.local_storage"
fi

echo "Alembic upgrade head…"
(
  cd "${ROOT}/backend"
  "${ROOT}/backend/.venv/bin/alembic" upgrade head
)

echo "Seeding BeTaxed staff…"
(
  cd "${ROOT}/backend"
  export ENV="${ENV:-DEV}"
  export FIREBASE_AUTH_EMULATOR_HOST="${FIREBASE_AUTH_EMULATOR_HOST:-127.0.0.1:9099}"
  PYTHONPATH=. "$PY" scripts/seed_betaxed_staff.py
)

echo "Local reset done."
