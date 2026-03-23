#!/usr/bin/env bash
set -euo pipefail

MODEL_DIR="${MODEL_DIR:-/models}"
PORT="${PORT:-8000}"

if [[ ! -d "${MODEL_DIR}" ]]; then
  echo "[ERROR] 模型目录不存在: ${MODEL_DIR}" >&2
  exit 1
fi

exec uvicorn --factory server.app:create_app --host 0.0.0.0 --port "${PORT}"
