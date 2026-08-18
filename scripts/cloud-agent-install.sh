#!/usr/bin/env bash
# Idempotent repository bootstrap for the BeTaxed Cloud Agent environment.
# Refreshes backend (Python venv) and frontend (npm) dependencies after checkout.
# Safe to run repeatedly. Does NOT require a running database.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Python 3.13 and Node 24 are provided by the base environment. Node 24 lives at
# /usr/bin/node; keep it ahead of any nvm-managed Node on PATH for frontend work.
PY="${BETAXED_PYTHON:-python3.13}"
NODE_BIN_DIR="${BETAXED_NODE_BIN_DIR:-/usr/bin}"

echo "[install] Backend: virtualenv + pip install"
cd "$REPO_ROOT/backend"
[ -f .env ] || cp .env.dev.example .env
if [ ! -x .venv/bin/python ]; then
  "$PY" -m venv .venv
fi
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt

echo "[install] Frontend: npm ci"
cd "$REPO_ROOT/frontend"
[ -f .env.local ] || cp .env.example .env.local
export PATH="$NODE_BIN_DIR:$PATH"
npm ci --no-audit --no-fund

echo "[install] Done"
