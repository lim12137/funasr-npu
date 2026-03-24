# 2026-03-24 模型来源与准备手册落地计划

## 目标

在当前仓库补齐“模型来源与准备手册”，明确区分上游官方步骤与本仓库部署约定，并给出可直接复制执行的命令。

## 实施步骤（简）

1. 复核上游 `HaujetZhao/Fun-ASR-GGUF` 当前 `master` README（以 `02c11cb093af8e01bc6f4580639b3663a41b74c0` 为锚点）中的模型下载与导出流程。
2. 基于本仓库 `scripts/run-funasr-infer.py` / `server/app.py` / `compose.yaml` 梳理模型文件名要求、挂载路径与最小校验方式。
3. 新增 `docs/model-source.md`，按“官方明确步骤”与“本仓库约定/推断”两块组织，并附可复制命令。
4. 更新 `README.md` 与 `docs/model-layout.md` 的跳转链接，确保读者能从入口文档直达新手册。
5. 执行最小验证（文档存在、静态检查可执行即执行、`git status --short --branch`），完成提交与推送。
