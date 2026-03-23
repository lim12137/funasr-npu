# 2026-03-23 GHCR 镜像构建实施计划

## 目标

在空仓库中落地最小可执行的 910B 容器方案，并通过 GitHub Actions 自动构建并推送至 GHCR。

## 输入约束

1. 基础镜像采用昇腾 910B Runtime（CANN 8.0 RC1）。
2. Workflow 需支持 `push`（默认分支）与 `workflow_dispatch`。
3. 镜像标签至少包括 `sha`、分支名、默认分支 `latest`。
4. 登录 GHCR 使用 `GITHUB_TOKEN`。

## 执行步骤

1. 在 `D:/Agent/work/funasr-npu` 初始化/重建仓库工作区并关联远端。
2. 提炼 `todo.txt` 方案，沉淀最小可运行 `Dockerfile`（安装基础运行依赖与 Ascend 环境变量）。
3. 增加 `.dockerignore` 减少无关构建上下文。
4. 新增 GitHub Actions workflow 完成 GHCR 登录、元数据生成、Buildx 构建与推送。
5. 编写 `README.md` 说明本地构建、Action 触发、镜像地址与标签策略。
6. 进行最小自检并记录到验收报告。
7. 本地提交并推送远端默认分支，尝试触发 workflow 并回收执行摘要。

## 验收标准

1. 关键文件齐全：`Dockerfile`、`.dockerignore`、`.github/workflows/*.yml`、`README.md`、`docs/*`。
2. `git status` 显示工作区干净（提交后）。
3. 若环境具备 `docker` / `actionlint` / `gh`，执行可行性验证并有结果记录。
4. 推送成功后可看到对应 workflow 记录（自动或手动触发）。
