#!/bin/bash
set -euo pipefail
if [ "$#" -ne 0 ]; then
  echo "用法：bash scripts/restart-local.sh" >&2
  exit 2
fi
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$DIR/restart_local.py"
