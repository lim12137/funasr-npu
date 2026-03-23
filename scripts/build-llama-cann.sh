#!/usr/bin/env bash
set -euo pipefail

LLAMA_SRC_DIR="${LLAMA_SRC_DIR:-/workspace/llama.cpp}"
LLAMA_REF="${LLAMA_REF:-master}"

echo "[INFO] clone ggml-org/llama.cpp (${LLAMA_REF}) -> ${LLAMA_SRC_DIR}"
if [[ -d "${LLAMA_SRC_DIR}/.git" ]]; then
  git -C "${LLAMA_SRC_DIR}" fetch --depth 1 origin "${LLAMA_REF}"
  git -C "${LLAMA_SRC_DIR}" checkout "${LLAMA_REF}"
else
  git clone --depth 1 --branch "${LLAMA_REF}" https://github.com/ggml-org/llama.cpp.git "${LLAMA_SRC_DIR}"
fi

echo "[INFO] configure with CANN backend"
cmake -S "${LLAMA_SRC_DIR}" -B "${LLAMA_SRC_DIR}/build-cann" -DGGML_CANN=on

echo "[INFO] build"
cmake --build "${LLAMA_SRC_DIR}/build-cann" -j"$(nproc)"

echo "[INFO] done"
