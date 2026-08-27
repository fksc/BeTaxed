#!/bin/sh
# Persist Auth emulator users on SIGTERM (compose stop/down).
# Export into a subdirectory: firebase cannot replace a Docker volume mountpoint
# (EBUSY on /emulator-data).
set -eu
DATA_ROOT="${FIREBASE_EMULATOR_DATA:-/emulator-data}"
EXPORT_DIR="${DATA_ROOT}/export"
mkdir -p "$EXPORT_DIR"
set -- --only auth --project demo-betaxed --export-on-exit="$EXPORT_DIR"
if [ -f "$EXPORT_DIR/firebase-export-metadata.json" ]; then
  set -- "$@" --import="$EXPORT_DIR"
fi
exec firebase emulators:start "$@"
