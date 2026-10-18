#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$SCRIPT_DIR:${PYTHONPATH:-}"
cd "$SCRIPT_DIR"
exec /usr/bin/python3 -m backend.dbus_service
