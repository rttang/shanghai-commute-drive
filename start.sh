#!/bin/bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
if [ "$#" -eq 1 ] && [ "${1:-}" = "--preview" ]; then
  if [ ! -f dist/index.html ]; then
    echo "请先运行 npm run build，再启动稳定预览。" >&2
    exit 1
  fi
  set -- preview
elif [ "$#" -gt 0 ]; then
  echo "用法：bash start.sh [--preview]" >&2
  exit 1
fi
if ! command -v node >/dev/null 2>&1; then
  echo "需要 Node.js 20.19 或更新版本。" >&2
  exit 1
fi
if [ ! -f node_modules/vite/bin/vite.js ]; then
  echo "请先运行 npm ci --no-bin-links --cache .tooling/npm-cache 安装项目依赖。" >&2
  exit 1
fi
if lsof -nP -iTCP:8080 -sTCP:LISTEN -t >/dev/null; then
  echo "8080 端口已有服务。请确认 http://127.0.0.1:8080/；本脚本不终止已有进程。" >&2
  exit 1
fi
echo "上海漫游：http://127.0.0.1:8080/"
exec python3 scripts/storage_guard.py run -- node node_modules/vite/bin/vite.js "$@" --host 127.0.0.1 --port 8080 --strictPort
