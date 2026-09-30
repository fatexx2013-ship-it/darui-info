#!/usr/bin/env bash
# 本地一键：抓取最新数据 + 打开预览
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> 抓取数据"
python3 scripts/update_data.py "$@"

echo "==> 打开本地预览（file:// 直读 docs/index.html）"
if command -v open >/dev/null 2>&1; then
  open docs/index.html
else
  echo "请手动打开：$(pwd)/docs/index.html"
fi
