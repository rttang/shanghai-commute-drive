#!/bin/bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "$PROJECT_DIR/scripts/blender-local.sh" --background --python-exit-code 1 --python "$PROJECT_DIR/scripts/build_tourism_models.py"
