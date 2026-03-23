# funasr-npu

最小可执行仓库：基于昇腾 910B Runtime 的容器镜像构建，并通过 GitHub Actions 自动推送到 GHCR。

## 镜像地址

- `ghcr.io/lim12137/funasr-npu`

## 本地构建

```bash
docker build -t funasr-npu:local .
```

## 本地运行（示例）

```bash
docker run --rm -it \
  --device=/dev/davinci0 \
  --device=/dev/davinci_manager \
  --device=/dev/devmm_svm \
  --device=/dev/hisi_hdc \
  funasr-npu:local
```

## GitHub Actions 触发方式

- 推送到默认分支（`main`）会自动触发构建与推送。
- 在 GitHub 仓库页面手动触发：`Actions` -> `Build and Push GHCR Image` -> `Run workflow`。

## SWR 可选登录（用于基础镜像拉取鉴权）

Dockerfile 基础镜像来自：

- `swr.cn-south-1.myhuaweicloud.com/ascendhub/ascend-runtime:8.0.rc1-910B-ubuntu22.04`

如果该镜像仓库对匿名访问返回 `401 Unauthorized`，请在仓库 `Settings -> Secrets and variables -> Actions` 配置以下 secrets：

- `SWR_REGISTRY`（例如：`swr.cn-south-1.myhuaweicloud.com`）
- `SWR_USERNAME`
- `SWR_PASSWORD`

Workflow 会自动检测这三个 secrets：

- 三者齐全：先登录 SWR，再构建镜像；
- 任一缺失：跳过 SWR 登录并给出 warning（此时若仓库需要鉴权，构建会在 `FROM` 拉取阶段失败）。

## 标签策略

- `sha-<commit>`
- `<branch>`（例如 `main`）
- `latest`（仅默认分支）
