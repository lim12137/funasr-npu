# syntax=docker/dockerfile:1.7
FROM ascendai/cann:8.5.0-910b-ubuntu22.04-py3.11

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    ffmpeg \
    libsndfile1 \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

ENV ASCEND_TOOLKIT_HOME=/usr/local/Ascend/ascend-toolkit/latest \
    ASCEND_GLOBAL_WORKSPACE_SIZE=2048 \
    PATH=/usr/local/Ascend/ascend-toolkit/latest/bin:${PATH} \
    LD_LIBRARY_PATH=/usr/local/Ascend/ascend-toolkit/latest/lib64:${LD_LIBRARY_PATH} \
    PYTHONUNBUFFERED=1 \
    MODEL_DIR=/models \
    PORT=8000

COPY requirements.txt /workspace/requirements.txt
RUN python3 -m pip install --no-cache-dir -r /workspace/requirements.txt

COPY server /workspace/server
COPY scripts/start-server.sh /workspace/scripts/start-server.sh

RUN chmod +x /workspace/scripts/start-server.sh \
    && mkdir -p /models

EXPOSE 8000

CMD ["/workspace/scripts/start-server.sh"]
