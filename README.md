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

## 标签策略

- `sha-<commit>`
- `<branch>`（例如 `main`）
- `latest`（仅默认分支）
