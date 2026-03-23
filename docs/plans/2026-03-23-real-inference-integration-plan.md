# 2026-03-23 `/asr` 真实推理链路接入计划

## 目标

将 FastAPI `POST /asr` 从占位响应改为真实推理入口：接收上传音频、落盘临时文件、通过外部命令调用 Fun-ASR-GGUF 推理脚本、解析结果并返回结构化响应；同时补齐错误处理与清理逻辑，确保容器内具备可执行的真实命令链路。

## 上游核对结论（先决条件）

> 结论：`D:/Agent/deepseek/技能/docs/todo.txt` 中的 `infer.py` / `download_model.py` / `li-plus/llama.cpp@ascend-backend` 路线已过期，按上游当前结构调整实施。

### Fun-ASR-GGUF（`HaujetZhao/Fun-ASR-GGUF`）

- 已核对 `HEAD=02c11cb093af8e01bc6f4580639b3663a41b74c0`。
- 上游当前**不存在** `infer.py` 与 `download_model.py`（仓库脚本为 `06-Inference.py` 等）。
- 推理入口当前以 Python API 为主（`fun_asr_gguf.FunASREngine` + `ASREngineConfig`），`06-Inference.py` 为示例脚本，非参数化 CLI。
- 因结构变更，原“直接接 `infer.py` 并改 `--cuda -> --ascend`”路线需调整为：
  - 在本仓库新增薄封装 CLI（仅参数透传 + 调用上游 API，不重写推理核心）；
  - FastAPI 通过外部命令调用该 CLI。

### llama.cpp（`li-plus/llama.cpp` 与 CANN 现状）

- 已核对 `li-plus/llama.cpp` 默认分支 `master=f7d278faf308cb989c221895968f2a26f14b2155`。
- 该仓库当前无 `ascend-backend` 分支，且源码不含 CANN 相关选项，原分支路径已失效。
- 根据 `ggml-org/llama.cpp` 当前文档，CANN 现由主线提供，编译选项为 `-DGGML_CANN=on`，并有 `docs/backend/CANN.md` 对应构建与运行说明。
- 因此容器中将以“可选 CANN 构建路径”替代已失效的 `li-plus/llama.cpp@ascend-backend` 固定路径，并在文档中明确该上游变化与兼容策略。

## TDD 实施步骤

1. 先写失败测试（红灯）：
   - `/asr` 能组装并调用外部推理命令（含音频路径、模型目录、可选参数）。
   - 外部命令失败时返回结构化错误（含退出码/超时/stderr 摘要）。
   - 上传文件会落盘，且请求结束后临时文件必清理。
2. 最小实现（绿灯）：
   - 新增命令执行模块与配置解析；
   - 改造 `POST /asr` 为 `multipart/form-data` 上传；
   - 接入外部命令执行与 JSON 结果解析。
3. 重构与增强：
   - 提炼命令组装函数，便于测试；
   - 统一错误码与响应结构；
   - 保持现有 `/healthz` 行为不变。
4. 容器与脚本补齐：
   - 新增/更新推理包装脚本；
   - Dockerfile 增加上游拉取与依赖准备；
   - Compose/README 补充运行参数与挂载要求。
5. 验证与留痕：
   - 执行 `pytest`、`docker compose config`、上游只读核对命令；
   - 将命令与结果摘要落盘到 `docs/reports/2026-03-23-action-build-report.md`。

## 计划改动文件

- `server/app.py`
- `server/*`（新增推理命令执行模块）
- `scripts/*`（新增 Fun-ASR 外部调用脚本）
- `tests/test_api.py`
- `Dockerfile`
- `compose.yaml`
- `README.md`
- `docs/reports/2026-03-23-action-build-report.md`

## 验收标准

- 单测通过，覆盖命令组装、错误处理、文件清理三个核心行为。
- `POST /asr` 可接收音频文件并触发真实外部推理命令链路。
- 若本机无 910B 条件，需明确“未完成实机推理”的客观证据与阻塞点，但命令链路与错误返回完整可验证。
- 变更提交到 `main` 并推送，记录最新 commit SHA 与 workflow 状态。
