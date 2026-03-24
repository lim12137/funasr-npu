# 模型来源与准备手册

本文档用于说明：`funasr-npu` 运行所需模型文件从哪里来、上游未直接给成品时如何按官方流程生成、以及如何落到本仓库 `./models` 并做最小校验。

## 版本锚点与信息来源

- **官方来源（明确给出）**
  - `HaujetZhao/Fun-ASR-GGUF` 仓库 README（分支 `master`，当前 `HEAD=02c11cb093af8e01bc6f4580639b3663a41b74c0`）。
  - README 中的“下载与导出模型”与“导出与量化流程 (6 步走)”。
- **本仓库约定（代码行为）**
  - `scripts/run-funasr-infer.py` 的默认文件名候选与查找顺序。
  - `server/app.py` / `scripts/start-server.sh` / `compose.yaml` 对 `MODEL_DIR=/models` 与挂载 `./models:/models:ro` 的要求。

---

## 一、官方明确给出的步骤（原样遵循）

> 这一节只列上游 README 明确出现过的流程与命令。

1. 安装依赖：

```bash
pip install -r requirements.txt
```

2. 安装并下载原始模型（ModelScope）：

```bash
pip install modelscope
modelscope download --model FunAudioLLM/Fun-ASR-Nano-2512
```

3. 执行 6 步导出/量化流程（README 给出的脚本顺序）：

```bash
python 01-Export-ONNX-FP32.py
python 02-Optimize-ONNX.py
python 03-Quantize-ONNX.py
python 04-Export-Decoder-GGUF-FP16.py
python 05-Quantize-Decoder-GGUF.py
python 06-Inference.py
```

4. README 给出的导出结果目录示例是 `model/`，文件示例包含：
   - `Fun-ASR-Nano-Encoder-Adaptor.int4.onnx`
   - `Fun-ASR-Nano-CTC.int4.onnx`
   - `Fun-ASR-Nano-Decoder.q5_k.gguf`
   - `tokens.txt`

---

## 二、本仓库部署约定 / 推断（基于当前代码）

> 这一节是 `funasr-npu` 当前实现要求，不是上游 README 的直接承诺。

1. **模型放置位置**
   - 宿主机目录：`./models`
   - 容器内目录：`/models`（由 `compose.yaml` 挂载）
   - 若目录不存在，服务启动失败（`scripts/start-server.sh` / `server/app.py` 会校验目录存在）。

2. **最小必需文件（每类命中一个）**
   - Encoder：`Fun-ASR-Nano-Encoder-Adaptor.int4.onnx` 或 `Fun-ASR-Nano-Encoder-Adaptor.fp16.onnx`
   - CTC：`Fun-ASR-Nano-CTC.int4.onnx` 或 `Fun-ASR-Nano-CTC.fp16.onnx`
   - Decoder：`Fun-ASR-Nano-Decoder.q5_k.gguf` 或 `Fun-ASR-Nano-Decoder.q4_k.gguf`
   - Tokens：`tokens.txt`

3. **默认候选优先级（`scripts/run-funasr-infer.py`）**
   - Encoder：`int4` 优先，`fp16` 兜底
   - CTC：`int4` 优先，`fp16` 兜底
   - Decoder：`q5_k` 优先，`q4_k` 兜底

4. **HTTP API 限制（当前实现）**
   - `POST /asr` 不支持通过请求覆盖 `encoder/ctc/decoder/tokens` 文件路径；
   - 因此部署上必须把文件名准备成上述默认候选之一。

---

## 三、可复制落地命令（从上游生成并接入本仓库）

以下命令假设你在宿主机已具备 Python 环境，并从 `D:/Agent/work/funasr-npu` 目录执行。

### 1) 拉取上游并切到当前锚点

```powershell
Set-Location D:/Agent/work
git clone https://github.com/HaujetZhao/Fun-ASR-GGUF.git
Set-Location D:/Agent/work/Fun-ASR-GGUF
git checkout 02c11cb093af8e01bc6f4580639b3663a41b74c0
```

### 2) 按官方 README 执行模型下载与导出

```powershell
pip install -r requirements.txt
pip install modelscope
modelscope download --model FunAudioLLM/Fun-ASR-Nano-2512
python 01-Export-ONNX-FP32.py
python 02-Optimize-ONNX.py
python 03-Quantize-ONNX.py
python 04-Export-Decoder-GGUF-FP16.py
python 05-Quantize-Decoder-GGUF.py
python 06-Inference.py
```

> 说明：上游 `export_config.py` 默认 `EXPORT_DIR=./model`，因此导出的模型文件默认落在 `D:/Agent/work/Fun-ASR-GGUF/model`。

### 3) 拷贝到本仓库 `./models`

```powershell
Set-Location D:/Agent/work/funasr-npu
New-Item -ItemType Directory -Force models | Out-Null
Copy-Item D:/Agent/work/Fun-ASR-GGUF/model/Fun-ASR-Nano-Encoder-Adaptor.*.onnx ./models/ -Force
Copy-Item D:/Agent/work/Fun-ASR-GGUF/model/Fun-ASR-Nano-CTC.*.onnx ./models/ -Force
Copy-Item D:/Agent/work/Fun-ASR-GGUF/model/Fun-ASR-Nano-Decoder.*.gguf ./models/ -Force
Copy-Item D:/Agent/work/Fun-ASR-GGUF/model/tokens.txt ./models/ -Force
```

---

## 四、最小校验

### 校验 1：文件完整性（本仓库约定）

```powershell
Set-Location D:/Agent/work/funasr-npu
Get-ChildItem ./models
```

期望至少能看到（每类命中一个即可）：`Encoder onnx`、`CTC onnx`、`Decoder gguf`、`tokens.txt`。

### 校验 2：快速推理链路（最小命令）

```powershell
python scripts/run-funasr-infer.py `
  --repo-dir D:/Agent/work/Fun-ASR-GGUF `
  --model-dir D:/Agent/work/funasr-npu/models `
  --audio-path D:/path/to/demo.wav `
  --output-json
```

若返回单行 JSON（包含 `text` 字段）即表示模型读取与推理链路最小可用。

### 校验 3：容器挂载与服务可见性（可选）

```bash
docker compose up --build -d
curl http://127.0.0.1:8000/healthz
```

返回中 `model_dir` 为 `/models`，表示挂载路径生效。
