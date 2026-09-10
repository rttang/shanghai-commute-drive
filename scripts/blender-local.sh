#!/bin/bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BLENDER_RUNTIME="$PROJECT_ROOT/.tooling/blender"
BLENDER_BIN="/Applications/Blender.app/Contents/MacOS/Blender"

python3 "$PROJECT_ROOT/scripts/storage_guard.py" check
if [ ! -x "$BLENDER_BIN" ]; then
    echo "Blender 尚未安装到 /Applications/Blender.app" >&2
    exit 1
fi
mkdir -p "$BLENDER_RUNTIME/tmp" "$BLENDER_RUNTIME/cache" \
    "$BLENDER_RUNTIME/user/config" "$BLENDER_RUNTIME/user/scripts" \
    "$BLENDER_RUNTIME/user/datafiles" "$BLENDER_RUNTIME/user/extensions"
export TMPDIR="$BLENDER_RUNTIME/tmp/"
export TMP="$TMPDIR"
export TEMP="$TMPDIR"
export XDG_CACHE_HOME="$BLENDER_RUNTIME/cache"
export PYTHONPYCACHEPREFIX="$BLENDER_RUNTIME/cache/python"
export PYTHONDONTWRITEBYTECODE=1
export BLENDER_USER_CONFIG="$BLENDER_RUNTIME/user/config"
export BLENDER_USER_SCRIPTS="$BLENDER_RUNTIME/user/scripts"
export BLENDER_USER_DATAFILES="$BLENDER_RUNTIME/user/datafiles"
export BLENDER_USER_EXTENSIONS="$BLENDER_RUNTIME/user/extensions"
cd "$PROJECT_ROOT/assets/blender"
exec python3 "$PROJECT_ROOT/scripts/blender_queue.py" -- python3 "$PROJECT_ROOT/scripts/storage_guard.py" run -- "$BLENDER_BIN" "$@"
