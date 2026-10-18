#!/usr/bin/env bash
# Fast statusline collector wrapper for Token Monitor for Claude Code
TARGET="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "$TARGET")" && pwd)"
export PYTHONPATH="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m backend.cli collect "$@"
