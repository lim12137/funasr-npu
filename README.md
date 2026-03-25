# funasr-npu

基于 Ascend 910B 运行时的 FastAPI HTTP 服务。当前版本已将 `POST /asr` 接入真实外部推理链路：上传音频后调用 `scripts/run-funasr-infer.py`，由该脚本使用 `HaujetZhao/Fun-ASR-GGUF` 当前 Python API (`fun_asr_gguf.FunASREngine`) 执行推理。

## 上游路线变更说明（2026-03-23）

- 早期待办记录中的“`infer.py` + `download_model.py` + `li-plus/llama.cpp@ascend-backend`”路线已过期。
- 复核结果：
  - `HaujetZhao/Fun-ASR-GGUF` 当前 `HEAD=02c11cb...` 不存在 `infer.py`、`download_model.py`；
  - `li-plus/llama.cpp` 当前无 `ascend-backend` 分支。
- 因此本仓库改为按上游现状接入：FastAPI -> 外部脚本 -> `fun_asr_gguf` API。

## 一条命令启动

### NPU（默认）

在仓库根目录执行：

```bash
docker compose up --build -d
```

### CPU

CPU 环境请改用 `compose.cpu.yaml`：

```bash
docker compose -f compose.cpu.yaml up --build -d
```

> 默认配置映射端口 `8000:8000`，并挂载宿主机 `./models` 到容器 `/models`（只读）。启动前宿主机必须存在 `./models` 目录（可为空）；若目录不存在，挂载失败会导致服务启动失败。模型来源与准备流程见 [docs/model-source.md](docs/model-source.md)，模型文件布局详见 [docs/model-layout.md](docs/model-layout.md)。

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

- `500`：`UPLOAD_IO_FAILED`（上传文件落盘失败）
- `502`：`INFERENCE_COMMAND_FAILED`（外部命令退出码非 0）
- `504`：`INFERENCE_COMMAND_TIMEOUT`（命令超时）

`mp3/m4a` 上传会通过 `ffmpeg` 自动转码为 `16k/mono PCM WAV` 后推理。

## WebSocket 兼容协议（FUNASR_EXTERNAL_API_DOC）

在不影响现有 HTTP `GET /healthz`、`POST /asr` 使用方式的前提下，服务支持与 `FUNASR_EXTERNAL_API_DOC.md` 对齐的 WebSocket 交互约定。完整字段说明见 [docs/external-ws-compat.md](docs/external-ws-compat.md)。

- 连接地址（root path 与 `/ws` 均可用）：
  - `ws://<host>:10095/`（推荐，用于兼容旧客户端默认端口）
  - `ws://<host>:10095/ws`
  - `ws://<host>:8000/`（同样可用）
  - `ws://<host>:8000/ws`
- WebSocket 子协议兼容：
  - 若客户端请求 `Sec-WebSocket-Protocol: binary`，服务端会回选 `binary`
- 建议使用当前 `compose.yaml` 同时映射：
  - `8000:8000`
  - `10095:8000`
- 消息帧顺序：
  1. 首帧：JSON（开始/配置）
  2. 中间帧：binary 音频数据（可分片多帧）
  3. 结束帧：JSON（结束标记）
- 返回字段（兼容约定）：
  - `text`
  - `mode`
  - `wav_name`

## 模型目录要求（摘要）

- 宿主机 `./models` 目录必须存在（Compose 会将其挂载到容器 `/models`）。
- 当前代码默认从 `/models` 读取模型文件；目录缺失时服务启动即失败。
- 模型来源、官方导出流程与落地命令见 [docs/model-source.md](docs/model-source.md)。
- 详细文件清单、候选优先级、目录示例与错误排查见 [docs/model-layout.md](docs/model-layout.md)。

## Compose 默认配置说明

- 服务名：`funasr-api`
- 镜像入口：`/workspace/scripts/start-server.sh`（容器启动即拉起 Uvicorn）
- 设备映射：`/dev/davinci0`、`/dev/davinci_manager`、`/dev/devmm_svm`、`/dev/hisi_hdc`
- 关键环境变量：
  - `MODEL_DIR=/models`
  - `ASR_ONNX_PROVIDER=NPU`（可选 `CPU`；NPU 模式要求 onnxruntime 支持 `CANNExecutionProvider`，否则推理脚本会报错并打印 `onnxruntime.get_available_providers()`）
  - `ASR_NPU_EXECUTION_PROVIDER=CANNExecutionProvider`（可选，默认 `CANNExecutionProvider`）
  - `ASR_COMMAND_TIMEOUT_SECONDS=600`
  - `ASR_UPLOAD_DIR=/tmp/funasr-upload`
  - `PORT=8000`

## Uvicorn Workers（多进程）

- 通过环境变量 `UVICORN_WORKERS` 配置 Uvicorn 多进程 workers，最大 4。
- 空字符串/全空白视为未设置，默认 `4`。
- 非整数会直接报错退出；`<=0` 视为 `1`，`>=4` 视为 `4`。
- 示例：`UVICORN_WORKERS=2 docker compose up --build -d`

## 关键环境变量（当前代码）

以下变量由 `server/app.py` 读取，且在镜像构建时由 `Dockerfile` 提供默认值（`compose.yaml` 可覆盖其中部分）：

- `FUNASR_REPO_DIR`：默认 `/workspace/Fun-ASR-GGUF`。服务会把它作为 `--repo-dir` 传给 `scripts/run-funasr-infer.py`，应指向上游 Fun-ASR-GGUF 仓库目录。
- `ASR_INFER_SCRIPT`：默认 `/workspace/scripts/run-funasr-infer.py`。用于指定外部推理脚本路径。
- `ASR_PYTHON_BIN`：默认 `python3`。用于启动外部推理脚本的 Python 可执行文件。
- `ASR_VULKAN_ENABLE`：默认不设置。若设置该变量，服务会向推理脚本追加 `--vulkan-enable <值>` 参数。
- `ASR_COMMAND_TIMEOUT_SECONDS`：默认 `600`。服务通过 `subprocess.run(..., timeout=...)` 限制推理命令时长，超时返回 `INFERENCE_COMMAND_TIMEOUT`（HTTP 504）。

## llama.cpp CANN 现状与对齐

- 旧的 `li-plus/llama.cpp@ascend-backend` 路径已失效（分支不存在）。
- 当前建议跟随 `ggml-org/llama.cpp` 主线 CANN 文档（`docs/backend/CANN.md`），使用 `-DGGML_CANN=on` 编译。
- 本仓库当前采用 Fun-ASR-GGUF 的 Python API 方式作为稳定集成入口；若需手工构建 CANN 版 llama.cpp，可按上游文档在目标机执行。

## 镜像信息

- 基础镜像：`ascendai/cann:8.5.0-910b-ubuntu22.04-py3.11`
- GHCR：`ghcr.io/lim12137/funasr-npu`
- 镜像 tag 选择：
  - NPU：`main` / `latest` / `sha-<shortsha>`
  - CPU：`main-cpu` / `cpu-latest` / `sha-<shortsha>-cpu`
