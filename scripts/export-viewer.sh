#!/usr/bin/env bash
# Re-export the Godot viewer WASM after changes to godot_viewer/viewer.gd or
# viewer.tscn. Writes the build into backend/app/static/godot/.
#
# Usage: scripts/export-viewer.sh [path-to-godot-binary]
#
# If no path is provided, the script falls back to `godot` on PATH.
set -euo pipefail

GODOT_BIN="${1:-${GODOT:-godot}}"

if ! command -v "$GODOT_BIN" >/dev/null 2>&1 && [ ! -x "$GODOT_BIN" ]; then
  echo "Godot binary not found: $GODOT_BIN" >&2
  echo "Pass it as arg 1, set \$GODOT, or put 'godot' on PATH." >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
"$GODOT_BIN" --headless \
  --path "$REPO_ROOT/godot_viewer" \
  --export-release "Web" \
  "$REPO_ROOT/backend/app/static/godot/viewer.html"
