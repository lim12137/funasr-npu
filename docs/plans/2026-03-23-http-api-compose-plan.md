# 2026-03-23 HTTP API + Docker Compose 实施计划

## 目标

在当前仓库落地 A1+B1 固定方案：基于 FastAPI 提供 HTTP API 服务，并通过 `docker compose` 一条命令启动。当前阶段仅提供服务骨架：

- `GET /healthz`：健康检查可用。
- `POST /asr`：返回结构化占位响应（明确尚未接入真实推理引擎）。
- 容器启动即启动服务（不再默认进入 bash）。
- 模型目录由宿主机挂载到容器 `/models`。
- 保留 Ascend 单卡常用设备映射与 `8000:8000` 端口映射。

## 变更范围

1. 新增服务代码：`server/app.py`、`server/__init__.py`。
2. 新增依赖与启动脚本：`requirements.txt`、`scripts/start-server.sh`。
3. 改造容器与编排：`Dockerfile`、`compose.yaml`。
4. 新增测试：`tests/test_api.py`（最小接口行为 + 模型目录检查）。
5. 文档更新：`README.md`、`docs/reports/2026-03-23-action-build-report.md`。

## TDD 执行步骤

1. **先测**：先编写最小测试用例并执行，预期失败（红灯）：
   - `GET /healthz` 返回 200 且状态字段为健康。
   - `POST /asr` 返回 501（或等价未实现语义）与占位消息。
   - 服务在缺失 `/models` 时按预期失败（通过环境变量注入测试目录）。
2. **实现**：补齐 FastAPI 应用、启动脚本、镜像入口与 compose。
3. **复测**：执行测试直至通过（绿灯）。
4. **文档**：补充一条命令部署与 API 调用示例，记录验证命令和结果摘要。

## 验收标准

- `pytest` 通过。
- `docker compose config` 可通过语法校验（若本机可用）。
- `git status` 干净后完成提交。
- 推送 `main` 成功，并记录最新 commit SHA。
- 若触发 GitHub Actions，记录 run 状态与链接。
