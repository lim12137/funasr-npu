# syntax=docker/dockerfile:1.7

ARG FUNASR_GGUF_REPO=https://github.com/HaujetZhao/Fun-ASR-GGUF.git
ARG FUNASR_GGUF_REF=02c11cb093af8e01bc6f4580639b3663a41b74c0

FROM python:3.11-slim-bookworm AS cpu-builder

WORKDIR /workspace

ARG FUNASR_GGUF_REPO
ARG FUNASR_GGUF_REF

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /workspace/requirements.txt
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r /workspace/requirements.txt \
    && /opt/venv/bin/pip install --no-cache-dir \
    numpy \
    scipy \
    pydub \
    gguf \
    rich \
    watchdog \
    pypinyin \
    srt \
    onnxruntime

RUN git clone --depth 1 ${FUNASR_GGUF_REPO} /workspace/Fun-ASR-GGUF \
    && git -C /workspace/Fun-ASR-GGUF fetch --depth 1 origin ${FUNASR_GGUF_REF} \
    && git -C /workspace/Fun-ASR-GGUF checkout ${FUNASR_GGUF_REF} \
    && rm -rf /workspace/Fun-ASR-GGUF/.git

FROM python:3.11-slim-bookworm AS cpu

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    ffmpeg \
    libsndfile1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:${PATH} \
    PYTHONUNBUFFERED=1 \
    MODEL_DIR=/models \
    FUNASR_REPO_DIR=/workspace/Fun-ASR-GGUF \
    ASR_INFER_SCRIPT=/workspace/scripts/run-funasr-infer.py \
    ASR_PYTHON_BIN=/opt/venv/bin/python \
    ASR_UPLOAD_DIR=/tmp/funasr-upload \
    ASR_ONNX_PROVIDER=CPU \
    ASR_COMMAND_TIMEOUT_SECONDS=600 \
    PORT=8000

COPY --from=cpu-builder /opt/venv /opt/venv
COPY --from=cpu-builder /workspace/Fun-ASR-GGUF /workspace/Fun-ASR-GGUF

COPY server /workspace/server
COPY scripts/start-server.sh /workspace/scripts/start-server.sh
COPY scripts/run-funasr-infer.py /workspace/scripts/run-funasr-infer.py
COPY scripts/build-llama-cann.sh /workspace/scripts/build-llama-cann.sh

RUN chmod +x /workspace/scripts/start-server.sh \
    && chmod +x /workspace/scripts/run-funasr-infer.py \
    && chmod +x /workspace/scripts/build-llama-cann.sh \
    && mkdir -p /models /tmp/funasr-upload

EXPOSE 8000

CMD ["/workspace/scripts/start-server.sh"]

FROM ascendai/cann:8.5.0-910b-ubuntu22.04-py3.11 AS npu-builder

WORKDIR /workspace

ARG FUNASR_GGUF_REPO
ARG FUNASR_GGUF_REF

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /workspace/requirements.txt
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r /workspace/requirements.txt \
    && /opt/venv/bin/pip install --no-cache-dir \
    numpy \
    scipy \
    pydub \
    gguf \
    rich \
    watchdog \
    pypinyin \
    srt \
    onnxruntime-cann==1.24.4

RUN git clone --depth 1 ${FUNASR_GGUF_REPO} /workspace/Fun-ASR-GGUF \
    && git -C /workspace/Fun-ASR-GGUF fetch --depth 1 origin ${FUNASR_GGUF_REF} \
    && git -C /workspace/Fun-ASR-GGUF checkout ${FUNASR_GGUF_REF} \
    && rm -rf /workspace/Fun-ASR-GGUF/.git

FROM ascendai/cann:8.5.0-910b-ubuntu22.04-py3.11 AS npu

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    ffmpeg \
    libsndfile1 \
    python3 \
    && rm -rf /var/lib/apt/lists/*

ENV ASCEND_TOOLKIT_HOME=/usr/local/Ascend/ascend-toolkit/latest \
    ASCEND_GLOBAL_WORKSPACE_SIZE=2048 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:/usr/local/Ascend/ascend-toolkit/latest/bin:${PATH} \
    LD_LIBRARY_PATH=/usr/local/Ascend/ascend-toolkit/latest/lib64:${LD_LIBRARY_PATH} \
    PYTHONUNBUFFERED=1 \
    MODEL_DIR=/models \
    FUNASR_REPO_DIR=/workspace/Fun-ASR-GGUF \
    ASR_INFER_SCRIPT=/workspace/scripts/run-funasr-infer.py \
    ASR_PYTHON_BIN=/opt/venv/bin/python \
    ASR_UPLOAD_DIR=/tmp/funasr-upload \
    ASR_ONNX_PROVIDER=CPU \
    ASR_COMMAND_TIMEOUT_SECONDS=600 \
    PORT=8000

COPY --from=npu-builder /opt/venv /opt/venv
COPY --from=npu-builder /workspace/Fun-ASR-GGUF /workspace/Fun-ASR-GGUF

COPY server /workspace/server
COPY scripts/start-server.sh /workspace/scripts/start-server.sh
COPY scripts/run-funasr-infer.py /workspace/scripts/run-funasr-infer.py
COPY scripts/build-llama-cann.sh /workspace/scripts/build-llama-cann.sh

RUN chmod +x /workspace/scripts/start-server.sh \
    && chmod +x /workspace/scripts/run-funasr-infer.py \
    && chmod +x /workspace/scripts/build-llama-cann.sh \
    && mkdir -p /models /tmp/funasr-upload

EXPOSE 8000

CMD ["/workspace/scripts/start-server.sh"]
