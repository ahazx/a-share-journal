#!/bin/bash
# A股复盘期刊 · 一键构建 + 发布
# 用法: ./publish.sh [源目录]
set -e

SRC="${1:-/Users/zhangxu/WorkBuddy/automation-2026-09-21-16-00-31/outputs}"
PY="$HOME/.workbuddy/binaries/python/versions/3.13.12/bin/python3"
cd "$(dirname "$0")"

echo "[1/3] 构建 HTML ..."
"$PY" build.py --src "$SRC"

echo "[2/3] 提交 ..."
git add -A
if git diff --cached --quiet; then
  echo "    无变更，跳过提交"
else
  git -c user.name=ahazx -c user.email=924292935@qq.com commit -q -m "复盘更新: $(date +%Y-%m-%d)"
  echo "    已提交"
fi

echo "[3/3] 推送 ..."
git push -q origin main && echo "    已推送 → https://ahazx.github.io/a-share-journal/"
