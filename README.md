# funasr-npu

基于 Ascend 910B 运行时的 FastAPI HTTP 服务骨架，支持通过 `docker compose` 一条命令启动。当前阶段 `/asr` 仅返回占位响应，尚未接入真实推理引擎。

## 一条命令启动

在仓库根目录执行：

```bash
docker compose up --build -d
```

> 默认使用 `compose.yaml` 的单卡配置，映射端口 `8000:8000`，并挂载宿主机 `./models` 到容器 `/models`（只读）。

## API 调用示例

健康检查：

```bash
curl http://127.0.0.1:8000/healthz
```

ASR 占位接口：

```bash
curl -X POST http://127.0.0.1:8000/asr \
  -H "Content-Type: application/json" \
  -d '{"audio_url":"https://example.com/demo.wav"}'
```

预期 `/asr` 返回 `501`，响应中包含“当前镜像仅提供服务骨架，未接入真实推理引擎”提示。

## Compose 默认配置说明

- 服务名：`funasr-api`
- 镜像入口：`/workspace/scripts/start-server.sh`（容器启动即拉起 Uvicorn）
- 设备映射：`/dev/davinci0`、`/dev/davinci_manager`、`/dev/devmm_svm`、`/dev/hisi_hdc`
- 关键环境变量：`MODEL_DIR=/models`、`PORT=8000`

## 镜像信息

- 基础镜像：`ascendai/cann:8.5.0-910b-ubuntu22.04-py3.11`
- GHCR：`ghcr.io/lim12137/funasr-npu`
