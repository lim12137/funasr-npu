#!/usr/bin/env bash
set -euo pipefail

MODEL_DIR="${MODEL_DIR:-/models}"
PORT="${PORT:-8000}"
DEFAULT_WORKERS=4

if [[ -z "${UVICORN_WORKERS+x}" ]]; then
  WORKERS="${DEFAULT_WORKERS}"
elif [[ "${UVICORN_WORKERS}" =~ ^[[:space:]]*$ ]]; then
  WORKERS="${DEFAULT_WORKERS}"
elif [[ "${UVICORN_WORKERS}" =~ ^[[:space:]]*-?[0-9]+[[:space:]]*$ ]]; then
  value="${UVICORN_WORKERS//[[:space:]]/}"
  if (( value <= 0 )); then
    WORKERS=1
  elif (( value >= 4 )); then
    WORKERS=4
  else
    WORKERS="${value}"
  fi
else
  echo "[ERROR] UVICORN_WORKERS 必须是整数: ${UVICORN_WORKERS}" >&2
  exit 1
fi

if [[ ! -d "${MODEL_DIR}" ]]; then
  echo "[ERROR] 模型目录不存在: ${MODEL_DIR}" >&2
  exit 1
fi

exec uvicorn --factory server.app:create_app --host 0.0.0.0 --port "${PORT}" --workers "$WORKERS"
