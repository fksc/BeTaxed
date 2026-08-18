#!/usr/bin/env bash
# Idempotent repository bootstrap for the BeTaxed Cloud Agent environment.
# Refreshes backend (Python venv) and frontend (npm) dependencies after checkout.
# Safe to run repeatedly. Does NOT require a running database.
# System toolchains (Python 3.13, Node 24, PostgreSQL 18, Redis 8) come from
# .cursor/Dockerfile — this script only installs repo packages.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Node 24 lives at /usr/bin/node in the Cloud Agent image; keep it ahead of nvm.
PY="${BETAXED_PYTHON:-python3.13}"
NODE_BIN_DIR="${BETAXED_NODE_BIN_DIR:-/usr/bin}"
export PATH="${NODE_BIN_DIR}:${PATH}"

if ! command -v "$PY" >/dev/null 2>&1; then
  echo "[install] ${PY} not found. Install Python 3.13 in .cursor/Dockerfile." >&2
  exit 127
fi
if ! command -v node >/dev/null 2>&1; then
  echo "[install] node not found. Install Node 24 in .cursor/Dockerfile." >&2
  exit 127
fi

echo "[install] Python: $($PY --version 2>&1)  Node: $(node --version)"

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
npm ci --no-audit --no-fund

echo "[install] Done"
