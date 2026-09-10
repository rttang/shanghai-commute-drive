#!/bin/bash
set -euo pipefail
STREET_PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$STREET_PROJECT"
python3 scripts/storage_guard.py check
export TMPDIR="$STREET_PROJECT/.tooling/blender/tmp/"
export XDG_CACHE_HOME="$STREET_PROJECT/.tooling/blender/cache"
export PYTHONDONTWRITEBYTECODE=1
node --import tsx scripts/prepare_street_placements.mjs
for generator in build_bund_district build_pudong_district build_street_furniture; do
  bash scripts/blender-local.sh --background --disable-autoexec --threads 2 \
    --python-exit-code 1 --python "$STREET_PROJECT/scripts/$generator.py"
done
node --import tsx scripts/build_street_context.mjs
python3 scripts/publish_street_references.py
python3 scripts/assemble_street_master.py
node --import tsx scripts/verify_photo_placement.mjs
node --import tsx scripts/verify_street_master_assets.mjs
bash scripts/blender-local.sh --background --disable-autoexec --threads 2 \
  --python-exit-code 1 --python "$STREET_PROJECT/scripts/save_street_master_blend.py"
