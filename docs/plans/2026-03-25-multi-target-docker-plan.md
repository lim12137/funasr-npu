# Multi-target Docker CPU/NPU Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 以最小改动完善 CPU/NPU 双镜像构建与发布，并更新 compose/README/报告。

**Architecture:** 保持现有多 target Dockerfile，CPU 与 NPU 分离依赖；NPU 镜像使用 onnxruntime-cann；compose 默认 NPU，CPU 走独立 compose；GHCR 输出两套 tag。

**Tech Stack:** Dockerfile 多阶段构建，GitHub Actions Buildx，FastAPI。

---

### Task 1: 更新 Dockerfile 的 NPU 依赖

**Files:**
- Modify: `Dockerfile`

**Step 1: 替换 NPU builder 依赖**

将 `npu-builder` 的 pip 安装列表里 `onnxruntime` 改为 `onnxruntime-cann==1.24.4`，CPU builder 保持不变。

**Step 2: 本地检查**

Run: `rg -n "onnxruntime" Dockerfile`  
Expected: NPU builder 为 `onnxruntime-cann==1.24.4`，CPU builder 为 `onnxruntime`

**Step 3: Commit**

```bash
git add Dockerfile
git commit -m "build: use onnxruntime-cann for npu image"
```

### Task 2: Compose 默认 provider 与 CPU 配置

**Files:**
- Modify: `compose.yaml`
- Modify: `compose.cpu.yaml`
- Add: `compose.cpu.yaml`（若未跟踪）

**Step 1: 修改默认 provider**

`compose.yaml` 中 `ASR_ONNX_PROVIDER` 设为 `NPU`，`compose.cpu.yaml` 保持 `CPU`。

**Step 2: Commit**

```bash
git add compose.yaml compose.cpu.yaml
git commit -m "chore: set compose defaults for cpu/npu"
```

### Task 3: README 使用说明

**Files:**
- Modify: `README.md`

**Step 1: 补充镜像与 compose 选择说明**

新增说明：
- NPU 默认使用 `compose.yaml`，并设置 `ASR_ONNX_PROVIDER=NPU`
- CPU 使用 `compose.cpu.yaml`
- GHCR tag：NPU `main/latest/sha-*`，CPU `main-cpu/cpu-latest/sha-*-cpu`

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: document cpu/npu images and tags"
```

### Task 4: 回归测试与报告

**Files:**
- Modify: `docs/reports/2026-03-25-ws-compat-test.md`

**Step 1: 运行最小回归**

Run: `pytest -q`  
Expected: 全量用例通过

**Step 2: 追加测试与 CI 结果摘要**

在报告中追加本次 `pytest -q` 输出摘要、tag 规则与 Actions run 结果。

**Step 3: Commit**

```bash
git add docs/reports/2026-03-25-ws-compat-test.md
git commit -m "test: record regression and ci summary"
```

### Task 5: CI 触发与结果确认

**Files:**
- None

**Step 1: 查看 Actions 运行**

Run: `gh run list --limit 5`  
Expected: 看到本次推送触发的 workflow

**Step 2: 查看 run 详情**

Run: `gh run view <run-id> --log`  
Expected: Build & push cpu/npu 两个 job 成功

---
