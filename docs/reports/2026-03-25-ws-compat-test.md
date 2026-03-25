# WebSocket 兼容协议测试报告（2026-03-25）

## 任务范围
- 新增 FastAPI WebSocket 入口，兼容离线 WS 协议基本流程：
  - 首帧 text JSON 配置
  - 中间 binary 音频分片
  - 结束 text JSON（`is_speaking:false` 或 `is_finished:true`）
  - 返回 text JSON 识别结果
- 复用现有 `/asr` 子进程推理链路（`_run_asr_command`）

## TDD 过程记录
### 1) 先写测试并验证失败（Red）
命令：

```bash
pytest -q tests/test_api.py -k ws_asr
```

关键输出：

```text
FF                                                                       [100%]
FAILED tests/test_api.py::test_ws_asr_accepts_is_speaking_false_end_frame
FAILED tests/test_api.py::test_ws_asr_accepts_is_finished_true_end_frame
```

失败原因摘要：当时服务尚未实现 `/ws`，WebSocket 连接被关闭。

### 2) 实现后回归（Green）
命令：

```bash
pytest -q tests/test_api.py -k ws_asr
```

关键输出：

```text
..                                                                       [100%]
2 passed, 8 deselected in 0.90s
```

覆盖点：
- 正常流程（配置帧 -> 音频二进制 -> `is_speaking:false` 结束）
- 结束帧另一种写法（`is_finished:true`）
- `hotwords` 输入兼容 `string` 与 `object`

### 3) 全量测试
命令：

```bash
pytest -q
```

关键输出：

```text
..........                                                               [100%]
10 passed in 1.25s
```

## 结果结论
- WebSocket 兼容入口已可用并通过测试。
- 返回结果至少包含 `text`、`mode`、`wav_name`，并附带 `wav_format`、`audio_fs`、`hotwords`、`result`、`engine`、`code` 字段用于兼容与调试。

## 追加回归（2026-03-25）
命令：

```bash
pytest -q
```

关键输出：

```text
...........                                                              [100%]
11 passed in 1.14s
```

新增覆盖点摘要：
- root path `/` 与 `/ws` 共用处理逻辑
- `Sec-WebSocket-Protocol: binary` 握手回选
- 非 RIFF bytes 自动封装为 WAV 后进入推理链路

## 追加回归（2026-03-25，mp3/m4a 兼容）
命令：

```bash
pytest -q
```

关键输出：

```text
.............                                                            [100%]
13 passed in 1.36s
```

新增覆盖点摘要：
- HTTP `/asr` 非 WAV 文件经 `ffmpeg` 自动转码为 WAV
- WebSocket `wav_format=mp3` 先落盘再转码进入推理链路

## workers 变更回归
命令：

```bash
pytest -q
```

关键输出：

```text
..............                                                           [100%]
14 passed in 1.27s
```

## 追加回归（2026-03-25，CPU/NPU provider 环境变量）
命令：

```bash
pytest -q
```

关键输出：

```text
..............                                                           [100%]
14 passed in 1.28s
```

变更点摘要：
- `ASR_ONNX_PROVIDER` 支持 `CPU/NPU`，并在 NPU 不可用时显式报错（打印 `onnxruntime.get_available_providers()`）。

补充调研结论：
- Ascend 对应 ONNX Runtime EP 名称：`CANNExecutionProvider`
- Python wheel 建议：`onnxruntime-cann`
- 上游 `Fun-ASR-GGUF@02c11cb` 未内置 CANN provider 映射：当前通过本仓库 `scripts/run-funasr-infer.py` 的 runtime monkeypatch 接入（或改上游实现）

验证命令（在目标运行环境执行）：

```bash
python -c "import onnxruntime as ort; print(ort.__version__); print(ort.get_available_providers())"
```
