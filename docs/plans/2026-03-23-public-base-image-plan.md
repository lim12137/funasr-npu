# 2026-03-23 公共基础镜像替换实施计划

## 变更原因

当前 `Dockerfile` 使用私有 SWR 基础镜像，GitHub Actions 在 `FROM` 阶段拉取失败（401 Unauthorized）。为消除鉴权依赖并恢复主干自动构建，需要改为公开可匿名拉取、且适配 Ascend 910B + Ubuntu 22.04 的镜像。

## 计划改动文件

1. `Dockerfile`：将基础镜像替换为公开 `ascendai/cann` 可用 tag。
2. `.github/workflows/build-and-push-ghcr.yml`：移除（或停用）SWR 可选登录与 warning 逻辑，保持 GHCR 构建链路最小化。
3. `README.md`：删除 SWR secrets 说明，补充新的公开基础镜像信息与验证方式。
4. `docs/reports/2026-03-23-action-build-report.md`：追加本次镜像可用性验证、工作流触发与结果。

## 验证方案

1. 只读验证：使用 `docker manifest inspect <image:tag>`（或等价只读命令）确认所选 tag 在公开仓库可访问。
2. CI 验证：推送到 `main` 并触发（或手动触发）`Build and Push GHCR Image`，收集最新 run 状态与链接。
3. 结果留痕：将关键命令与摘要追加到 `docs/reports/2026-03-23-action-build-report.md`。
