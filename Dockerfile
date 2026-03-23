# syntax=docker/dockerfile:1.7
FROM swr.cn-south-1.myhuaweicloud.com/ascendhub/ascend-runtime:8.0.rc1-910B-ubuntu22.04

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    ffmpeg \
    libsndfile1 \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

ENV ASCEND_TOOLKIT_HOME=/usr/local/Ascend/ascend-toolkit/latest \
    ASCEND_GLOBAL_WORKSPACE_SIZE=2048 \
    PATH=/usr/local/Ascend/ascend-toolkit/latest/bin:${PATH} \
    LD_LIBRARY_PATH=/usr/local/Ascend/ascend-toolkit/latest/lib64:${LD_LIBRARY_PATH}

CMD ["bash"]
