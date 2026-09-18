#!/usr/bin/env bash
# QuakeLogic HVSR Studio — macOS launcher (double-click in Finder)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
ARCH="$(uname -m)"; case "$ARCH" in arm64) PLAT="macos-arm64";; *) PLAT="macos-x64";; esac
if [ -x "$ROOT/runtime/$PLAT/python/bin/python3" ]; then PY="$ROOT/runtime/$PLAT/python/bin/python3";
elif [ -x "$ROOT/engine/.venv/bin/python" ]; then PY="$ROOT/engine/.venv/bin/python";
else PY="$(command -v python3)"; fi
if [ -z "${HVSR_PHP:-}" ] && [ -x "$ROOT/runtime/$PLAT/php/php" ]; then export HVSR_PHP="$ROOT/runtime/$PLAT/php/php"; fi
exec "$PY" "$ROOT/launcher/launch.py" "$@"
