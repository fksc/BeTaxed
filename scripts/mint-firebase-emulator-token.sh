#!/usr/bin/env bash
# Mint a Firebase Auth emulator ID token for local / cloud-agent testing.
# Usage: scripts/mint-firebase-emulator-token.sh [email] [password]
set -euo pipefail

EMAIL="${1:-hr@acme.example}"
PASSWORD="${2:-password}"
HOST="${FIREBASE_AUTH_EMULATOR_HOST:-127.0.0.1:9099}"
HOST="${HOST#http://}"
HOST="${HOST#https://}"

signup() {
  curl -sS -X POST \
    "http://${HOST}/identitytoolkit.googleapis.com/v1/accounts:signUp?key=fake-api-key" \
    -H 'Content-Type: application/json' \
    --data "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\",\"returnSecureToken\":true}"
}

signin() {
  curl -sS -X POST \
    "http://${HOST}/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=fake-api-key" \
    -H 'Content-Type: application/json' \
    --data "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\",\"returnSecureToken\":true}"
}

body="$(signup)"
if echo "${body}" | grep -q '"idToken"'; then
  echo "${body}"
  exit 0
fi
signin
