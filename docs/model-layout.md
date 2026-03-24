# 模型目录布局说明

本文档对应当前仓库实现（`server/app.py` + `scripts/run-funasr-infer.py`），用于说明 `MODEL_DIR`（默认 `/models`）下的文件布局要求。

如需查看“模型文件从哪里来、如何按上游官方流程生成并放入 `./models`”，请先阅读 [model-source.md](./model-source.md)。

## 最小必需文件清单

在默认配置下，模型目录至少需要以下 4 类文件（每类命中一个即可）：

1. Encoder ONNX：
   - `Fun-ASR-Nano-Encoder-Adaptor.int4.onnx`
   - 或 `Fun-ASR-Nano-Encoder-Adaptor.fp16.onnx`
2. CTC ONNX：
   - `Fun-ASR-Nano-CTC.int4.onnx`
   - 或 `Fun-ASR-Nano-CTC.fp16.onnx`
3. Decoder GGUF：
   - `Fun-ASR-Nano-Decoder.q5_k.gguf`
   - 或 `Fun-ASR-Nano-Decoder.q4_k.gguf`
4. Token 文件：
   - `tokens.txt`

## 默认文件名与候选优先级

当未显式传入 `scripts/run-funasr-infer.py` 的覆盖参数时，脚本按如下顺序查找：

- Encoder：`Fun-ASR-Nano-Encoder-Adaptor.int4.onnx` -> `Fun-ASR-Nano-Encoder-Adaptor.fp16.onnx`
- CTC：`Fun-ASR-Nano-CTC.int4.onnx` -> `Fun-ASR-Nano-CTC.fp16.onnx`
- Decoder：`Fun-ASR-Nano-Decoder.q5_k.gguf` -> `Fun-ASR-Nano-Decoder.q4_k.gguf`
- Tokens：仅 `tokens.txt`

如果传入 `--encoder` / `--ctc` / `--decoder` / `--tokens`：

- 绝对路径：直接使用；
- 相对路径：以 `--model-dir` 作为基准目录解析；
- 路径不存在：抛出 `FileNotFoundError` 并导致脚本非 0 退出。

## 推荐目录树示例

以下是与当前默认查找逻辑对齐的一种推荐布局（示例）：

```text
models/
├── Fun-ASR-Nano-Encoder-Adaptor.int4.onnx
├── Fun-ASR-Nano-CTC.int4.onnx
├── Fun-ASR-Nano-Decoder.q5_k.gguf
└── tokens.txt
```

容器部署时，默认通过 `compose.yaml` 挂载：

- 宿主机：`./models`
- 容器内：`/models`（只读）

## HTTP API 当前限制（参数覆盖）

当前 `POST /asr` 仅接收以下表单字段：

- `audio_file`（必填）
- `language`（可选）
- `context`（可选）
- `onnx_provider`（可选）

服务内部调用外部脚本时，不会透传 `--encoder` / `--ctc` / `--decoder` / `--tokens`。  
也就是说：当前 HTTP API **不支持**通过请求覆盖这 4 个模型文件参数；它始终按默认候选逻辑在 `MODEL_DIR` 中选取文件。

## 常见错误与排查

### 1) `UPLOAD_IO_FAILED`（HTTP 500）

触发位置：`server/app.py` 写入上传临时音频文件阶段。  
典型原因：

- `ASR_UPLOAD_DIR` 无法创建；
- 上传目录无写权限；
- 磁盘/文件系统写入异常。

### 2) 模型缺失（启动失败或推理失败）

可能表现为两类：

- 服务启动前失败：`MODEL_DIR` 不存在或不可访问，`create_app()` 抛 `FileNotFoundError`；
- 请求时失败：模型文件缺失导致推理脚本报错（如“模型文件不存在，候选: ...”），API 返回 `INFERENCE_COMMAND_FAILED`（HTTP 502）。

### 3) 权限问题

常见场景：

- `/tmp/funasr-upload`（或 `ASR_UPLOAD_DIR`）不可写，导致 `UPLOAD_IO_FAILED`；
- 模型目录或模型文件权限不足，推理脚本或推理引擎初始化失败，通常表现为 `INFERENCE_COMMAND_FAILED`（HTTP 502）。

排查建议：

1. 先确认目录存在：`./models`（宿主机）与容器内 `/models`；
2. 再确认文件名与候选优先级匹配；
3. 最后确认容器内上传目录和模型目录权限可读写（上传目录）/可读（模型目录）。
