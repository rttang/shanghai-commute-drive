#!/bin/bash
set -euo pipefail
STREETS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bash "$STREETS_ROOT/scripts/blender-local.sh" --background --disable-autoexec --python-exit-code 1 --python "$STREETS_ROOT/scripts/build_streetscape.py"
exec bash "$STREETS_ROOT/scripts/blender-local.sh" --background --disable-autoexec --python-exit-code 1 --python "$STREETS_ROOT/scripts/build_photo_architecture.py"
