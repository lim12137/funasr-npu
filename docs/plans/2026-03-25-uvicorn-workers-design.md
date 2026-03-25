# Uvicorn Workers 默认值与限幅设计

## 目标
- 默认未设置 `UVICORN_WORKERS` 时使用 4 workers。
- 若设置 `UVICORN_WORKERS`：仅允许整数；`<=0` 视为 1；`>=4` 视为 4；非整数报错退出。
- 通过 `exec uvicorn ... --workers "$WORKERS"` 启动。

## 范围
- 修改 `scripts/start-server.sh` 实现解析与限幅。
- 更新 `README.md` 补充说明与环境变量用法。
- 回归执行 `pytest -q`，并在报告追加结果。

## 行为设计
- 空字符串或全空白 → 视为未设置，默认 4。
- 含非空白但非整数 → 输出错误到 stderr 并退出码 1。
- 整数值范围裁剪：`<=0` → 1；`>=4` → 4；其余保持。

## 错误处理
- 非整数：输出 `[ERROR] UVICORN_WORKERS 必须是整数: <原值>` 并 `exit 1`。

## 测试策略
- 增加 pytest 测试，确保脚本包含解析逻辑与 `--workers "$WORKERS"` 启动行为。
- 最终执行全量 `pytest -q` 作为回归。
