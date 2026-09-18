#!/usr/bin/env bash
# QuakeLogic HVSR Studio — Linux launcher wrapper
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [ -x "$ROOT/runtime/linux-x64/python/bin/python3" ]; then PY="$ROOT/runtime/linux-x64/python/bin/python3";
elif [ -x "$ROOT/engine/.venv/bin/python" ]; then PY="$ROOT/engine/.venv/bin/python";
else PY="$(command -v python3)"; fi
export HVSR_PHP="${HVSR_PHP:-}"
if [ -z "$HVSR_PHP" ] && [ -x "$ROOT/runtime/linux-x64/php/php" ]; then export HVSR_PHP="$ROOT/runtime/linux-x64/php/php"; fi
exec "$PY" "$ROOT/launcher/launch.py" "$@"
