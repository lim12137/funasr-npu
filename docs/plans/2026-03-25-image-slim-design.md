<!--
设计文档：镜像瘦身（不破坏功能）
日期：2026-03-25
-->

# 镜像瘦身设计（Docker 多阶段）

## 背景
- 当前镜像基于 `ascendai/cann:8.5.0-910b-ubuntu22.04-py3.11`，在此基础上安装系统包、Python 依赖并 clone 外部仓库。
- 目标是在不影响功能的前提下，尽量缩小运行时镜像体积。

## 目标
- 运行时镜像更小。
- 不把模型打进镜像（继续 volume 挂载）。
- 维持原有启动与推理行为。
- 提供可量化的前后体积对比。

## 非目标
- 不改变业务逻辑与 API 行为。
- 不引入新的运行时依赖。

## 约束与约定
- 仅修改 `Dockerfile`、`.dockerignore`、`requirements*.txt`（必要时 `README.md`）。
- 可将测试依赖移出运行时镜像（使用 `requirements-dev.txt`）。
- 由于主要是配置文件改动，采用“验证命令”替代自动化测试（已获用户同意继续实施）。

## 方案选择
- **方案 2（推荐）**：多阶段构建（builder 装 git + 安装依赖 + clone 仓库；runtime 仅拷贝运行所需文件）。
- 理由：在保持功能一致的前提下显著减少运行时镜像体积，复杂度可控。

## 构建与运行流程
- `builder`：
  - `apt-get` 使用 `--no-install-recommends` 并清理 `apt` 缓存。
  - `pip install --no-cache-dir` 安装运行依赖。
  - shallow clone 外部仓库，checkout 指定 ref，删除 `.git`。
- `runtime`：
  - 不安装 `git`。
  - 拷贝 `site-packages` / `dist-packages`、外部仓库、`server/` 与 `scripts/`。
  - 保留原有 `CMD` 与环境变量。

## 关键变更点
- `requirements.txt`：仅运行依赖；新增 `requirements-dev.txt` 承载 `pytest`。
- `.dockerignore`：排除 `tests/`、`docs/` 等非运行时内容。
- `Dockerfile`：多阶段，减少层体积与无用内容。

## 风险与回退
- 风险：运行时缺少依赖或路径不匹配导致启动失败。
- 回退：恢复为单阶段 Dockerfile 或回滚到之前版本。

## 验证与交付
- 记录基线镜像大小。
- 构建新镜像并记录大小，对比差异。
- 运行容器验证 Uvicorn 正常启动日志。
