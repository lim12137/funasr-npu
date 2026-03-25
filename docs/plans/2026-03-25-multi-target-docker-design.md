# 多 Target 镜像与 CPU/NPU 路径设计（2026-03-25）

## 目标
- 将 Dockerfile 拆成 `cpu` 与 `npu` 两个 target，镜像体积优化并保持两条路径可用。
- NPU 镜像确保 `onnxruntime-cann` 可用，`ort.get_available_providers()` 包含 `CANNExecutionProvider`。
- GHCR 同时发布 NPU 与 CPU 两套 tag。
- Compose 保持 NPU 为默认，提供独立 CPU compose 入口。

## 方案
采用最小改动方案（A）：保留现有多 target 结构，仅在 `npu-builder` 中将 `onnxruntime` 替换为 `onnxruntime-cann==1.24.4`；CPU target 继续使用 `onnxruntime`。

## 影响范围
- `Dockerfile`：NPU builder 安装项调整。
- `compose.yaml` / `compose.cpu.yaml`：默认 provider 与 target 说明。
- `.github/workflows/build-and-push-ghcr.yml`：CPU/NPU tag 规则确认。
- `README.md`：说明如何选择镜像与 compose。
- `docs/reports/2026-03-25-ws-compat-test.md`：追加测试与 CI 结果摘要。

## 关键设计点
- NPU 镜像 tag 保持 `:main` / `:latest` / `:sha-*`。
- CPU 镜像 tag 使用 `:<branch>-cpu` / `:cpu-latest` / `:sha-*-cpu`。
- `compose.yaml` 默认 `ASR_ONNX_PROVIDER=NPU`，CPU 走 `compose.cpu.yaml`。

## 测试策略
- 至少执行 `pytest -q` 回归。
- CI 使用 `gh run list/view` 复核构建结果与 tag 产出。

## 风险与回滚
- 若 `onnxruntime-cann` 兼容性问题，可回退为原 `onnxruntime` 并禁用 NPU provider。
- CI 失败可在 GH Actions 重跑，保持 tag 规则不变。
