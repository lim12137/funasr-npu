# funasr-npu

基于 Ascend 910B 运行时的 FastAPI HTTP 服务。当前版本已将 `POST /asr` 接入真实外部推理链路：上传音频后调用 `scripts/run-funasr-infer.py`，由该脚本使用 `HaujetZhao/Fun-ASR-GGUF` 当前 Python API (`fun_asr_gguf.FunASREngine`) 执行推理。

## 上游路线变更说明（2026-03-23）

- `D:/Agent/deepseek/技能/docs/todo.txt` 中“`infer.py` + `download_model.py` + `li-plus/llama.cpp@ascend-backend`”路线已过期。
- 复核结果：
  - `HaujetZhao/Fun-ASR-GGUF` 当前 `HEAD=02c11cb...` 不存在 `infer.py`、`download_model.py`；
  - `li-plus/llama.cpp` 当前无 `ascend-backend` 分支。
- 因此本仓库改为按上游现状接入：FastAPI -> 外部脚本 -> `fun_asr_gguf` API。

## 一条命令启动

在仓库根目录执行：

```bash
docker compose up --build -d
```

> 默认配置映射端口 `8000:8000`，并挂载宿主机 `./models` 到容器 `/models`（只读）。启动前宿主机必须存在 `./models` 目录（可为空）；若目录不存在，挂载失败会导致服务启动失败。

## `/asr` 真实推理调用示例

健康检查：

```bash
curl http://127.0.0.1:8000/healthz
```

上传音频并推理：

```bash
curl -X POST http://127.0.0.1:8000/asr \
  -F "audio_file=@./demo.wav" \
  -F "language=中文" \
  -F "context=这是会议录音"
```

成功时返回 `200`，结构示例：

```json
{
  "code": "OK",
  "engine": "funasr-gguf",
  "result": {
    "text": "...",
    "segments": []
  }
}
```

失败时返回结构化错误：

- `502`：`INFERENCE_COMMAND_FAILED`（外部命令退出码非 0）
- `504`：`INFERENCE_COMMAND_TIMEOUT`（命令超时）

## 模型目录要求

`/models` 下需包含以下文件（名称可通过脚本参数覆盖）：

- `Fun-ASR-Nano-Encoder-Adaptor.int4.onnx`（或 `.fp16.onnx`）
- `Fun-ASR-Nano-CTC.int4.onnx`（或 `.fp16.onnx`）
- `Fun-ASR-Nano-Decoder.q5_k.gguf`（或 `.q4_k.gguf`）
- `tokens.txt`

## Compose 默认配置说明

- 服务名：`funasr-api`
- 镜像入口：`/workspace/scripts/start-server.sh`（容器启动即拉起 Uvicorn）
- 设备映射：`/dev/davinci0`、`/dev/davinci_manager`、`/dev/devmm_svm`、`/dev/hisi_hdc`
- 关键环境变量：
  - `MODEL_DIR=/models`
  - `ASR_ONNX_PROVIDER=CPU`
  - `ASR_COMMAND_TIMEOUT_SECONDS=600`
  - `ASR_UPLOAD_DIR=/tmp/funasr-upload`
  - `PORT=8000`

## llama.cpp CANN 现状与对齐

- 旧的 `li-plus/llama.cpp@ascend-backend` 路径已失效（分支不存在）。
- 当前建议跟随 `ggml-org/llama.cpp` 主线 CANN 文档（`docs/backend/CANN.md`），使用 `-DGGML_CANN=on` 编译。
- 本仓库当前采用 Fun-ASR-GGUF 的 Python API 方式作为稳定集成入口；若需手工构建 CANN 版 llama.cpp，可按上游文档在目标机执行。

## 镜像信息

- 基础镜像：`ascendai/cann:8.5.0-910b-ubuntu22.04-py3.11`
- GHCR：`ghcr.io/lim12137/funasr-npu`
