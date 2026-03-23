# 2026-03-23 GHCR 镜像构建验收报告

## 范围

- 仓库初始化与关键文件落地
- Docker 镜像构建链路（本地可行项）
- GitHub Actions 工作流配置有效性
- Git 提交、推送、工作流触发与结果收集

## 验证命令与结果摘要

### 1) 仓库状态与关键文件

```bash
git -C D:/Agent/work/funasr-npu status --short --branch
```

结果：`## main...origin/main`（工作区干净）

```bash
Test-Path D:/Agent/work/funasr-npu/Dockerfile
Test-Path D:/Agent/work/funasr-npu/.dockerignore
Test-Path D:/Agent/work/funasr-npu/.github/workflows/build-and-push-ghcr.yml
Test-Path D:/Agent/work/funasr-npu/README.md
Test-Path D:/Agent/work/funasr-npu/docs/plans/2026-03-23-ghcr-image-plan.md
Test-Path D:/Agent/work/funasr-npu/docs/reports/2026-03-23-action-build-report.md
```

结果：全部 `True`

### 2) 工具可用性检查

```bash
docker --version
actionlint --version
gh --version
```

结果摘要：

- `docker`：存在（`Docker version 28.0.1`）
- `actionlint`：未安装
- `gh`：存在（`gh version 2.88.1`）

### 3) 本地 Docker 可行性验证

```bash
docker build -t funasr-npu:local D:/Agent/work/funasr-npu
```

结果：失败，当前环境未运行 Docker daemon（`open //./pipe/docker_engine: The system cannot find the file specified`）。

### 4) Git 推送验证

```bash
git -C D:/Agent/work/funasr-npu push -u origin main
```

结果：成功，`main` 已推送并跟踪 `origin/main`。

### 5) GitHub Actions 触发与运行摘要

```bash
gh workflow list
gh run list --workflow "Build and Push GHCR Image" --limit 5
gh workflow run "Build and Push GHCR Image" --ref main
gh run view 23419933138 --json databaseId,event,status,conclusion,url
gh run view 23419947265 --json databaseId,event,status,conclusion,url
```

结果摘要：

- `push` 触发 run：`23419933138`，状态 `completed/failure`
- `workflow_dispatch` 手动触发 run：`23419947265`，状态 `completed/failure`

失败根因（摘录）：

```text
ERROR: failed to build: failed to solve:
swr.cn-south-1.myhuaweicloud.com/ascendhub/ascend-runtime:8.0.rc1-910B-ubuntu22.04:
failed to fetch anonymous token ... 401 Unauthorized
```

结论：Workflow 编排、登录 GHCR、标签生成逻辑均可执行；当前阻塞在基础镜像仓库 `swr.cn-south-1.myhuaweicloud.com` 的匿名拉取鉴权失败。

## 2026-03-23 复核补充（workflow 失败根因评审）

### 复核命令

```bash
gh run list -R lim12137/funasr-npu --workflow "Build and Push GHCR Image" --limit 10
gh run view 23420004007 -R lim12137/funasr-npu --log-failed
gh secret list -R lim12137/funasr-npu
```

### 复核结论

- 最新失败日志仍定位在 Dockerfile 第 2 行基础镜像拉取鉴权：`failed to fetch anonymous token ... 401 Unauthorized`。
- `gh secret list -R lim12137/funasr-npu` 当前为空，尚未配置 SWR 登录凭据。
- 已将 workflow 调整为“可选 SWR 登录”模式，约定 secrets：
  - `SWR_REGISTRY`
  - `SWR_USERNAME`
  - `SWR_PASSWORD`
- README 已同步补充 SWR secrets 配置说明与缺失时的预期失败行为。

## 2026-03-23 二次修复与复验记录

### 复验命令

```bash
gh run view 23420122141 -R lim12137/funasr-npu
gh run watch 23420161768 -R lim12137/funasr-npu --exit-status
gh run view 23420161768 -R lim12137/funasr-npu --json databaseId,status,conclusion,url,headSha
```

### 复验结果

- run `23420122141`：`This run likely failed because of a workflow file issue`（快速失败，无 job 明细）。
- workflow 已改为用 `env` 变量判定 SWR secrets 是否齐全，避免直接在 `if` 中判断 `secrets.*`。
- run `23420161768`：workflow 可正常进入 job。
  - `Log in to SWR (optional)` 被跳过；
  - `Warn when SWR secrets are missing` 正常输出 warning；
  - 最终仍在 Dockerfile `FROM` 基础镜像拉取阶段返回 `401 Unauthorized`（与根因一致）。

## 2026-03-23 公共基础镜像替换与复验记录

### 本次改动目标

- 将基础镜像从私有 SWR 替换为公开可拉取镜像，消除 `401 Unauthorized` 阻塞。
- 选用镜像：`ascendai/cann:8.5.0-910b-ubuntu22.04-py3.11`（910B + Ubuntu 22.04）。

### 验证命令

```bash
docker version
docker manifest inspect ascendai/cann:8.5.0-910b-ubuntu22.04-py3.11
git -C D:/Agent/work/funasr-npu push origin main
gh run list -R lim12137/funasr-npu --workflow "Build and Push GHCR Image" --limit 5
gh run view 23420798786 -R lim12137/funasr-npu --json databaseId,event,status,conclusion,url,headSha,displayTitle,jobs
```

### 结果摘要

- 本机 Docker 客户端可用，但 Docker daemon 未启动（`//./pipe/docker_engine` 不存在）。
- 本机执行 `docker manifest inspect` 受当前网络到 `registry-1.docker.io:443` 连接限制，未能直接完成只读校验。
- 推送 `main` 后触发 workflow run `23420798786`，最终 `completed/success`。
- `Validate public base image (readonly)` 步骤成功，说明 `ascendai/cann:8.5.0-910b-ubuntu22.04-py3.11` 在 GitHub Actions 环境可公开访问。
- `Build and push` 步骤成功，GHCR 推送链路恢复正常。

## 2026-03-23 最新成功状态对齐（run `23421104179`）

### 对齐命令

```bash
git -C D:/Agent/work/funasr-npu rev-parse HEAD
gh run view 23421104179 -R lim12137/funasr-npu --json databaseId,event,status,conclusion,url,headSha,displayTitle,createdAt,updatedAt
```

### 对齐结果

- 当前 `main` 分支 HEAD：`12bf413d357262d7a3826bb6030cf2a5bbbff1f4`。
- 最新成功 run：`23421104179`（`event=push`，`status=completed`，`conclusion=success`）。
- run 对应 `headSha=12bf413d357262d7a3826bb6030cf2a5bbbff1f4`，与当前 HEAD 一致。
- run 链接：`https://github.com/lim12137/funasr-npu/actions/runs/23421104179`。

### 阶段性结论澄清

- 文档中出现的 SWR/`401 Unauthorized` 相关记录属于历史失败阶段，发生于基础镜像仍指向私有 SWR 仓库时。
- 在将基础镜像替换为公开镜像后，主链路已恢复并持续成功；当前验收以 run `23421104179` 为准。
