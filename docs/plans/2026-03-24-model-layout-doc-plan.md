# 2026-03-24 模型目录文档落地计划（方案 2）

## 目标

在不改动现有代码行为的前提下，补齐模型目录说明文档，并让 README 快速启动路径可直达详细说明。

## 实施步骤（简）

1. 基于 `server/app.py` 与 `scripts/run-funasr-infer.py` 整理模型文件最小要求、默认文件名与候选优先级。
2. 更新 `README.md`：保留“一条命令启动”，明确宿主机 `./models` 必须存在，并链接 `docs/model-layout.md`。
3. 新增 `docs/model-layout.md`：补齐推荐目录树、HTTP API 参数覆盖限制、常见错误排查（含 `UPLOAD_IO_FAILED`、模型缺失、权限问题）。
4. 执行最小验证：确认文档文件存在，检查 `git diff --stat` 与 `git status --short --branch`。
