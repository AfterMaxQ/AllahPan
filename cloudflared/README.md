# Cloudflare Tunnel 配置

隧道 `Allahpan-win`（ID: `34641e20-8826-4545-bf00-df32c69a7cfb`）由 Docker 容器 `allahpan-cloudflared` 运行，通过 `network_mode: service:allahpan-nginx` 与 nginx 共享网络栈，使 Dashboard 远程配置中的 `http://localhost:88` 在容器内可达。

## 首次部署

1. 将 Cloudflare 下载的 credentials 放到 `cloudflared/credentials.json`（UTF-8 **无 BOM**，参考 [`credentials.json.example`](credentials.json.example)）
2. 停止宿主机 cloudflared：`Stop-Process -Name cloudflared -Force -ErrorAction SilentlyContinue`
3. 启动：`docker compose up -d --build nginx cloudflared`

## Dashboard 配置说明

当前隧道为 **remotely-managed** 模式，Cloudflare Dashboard 中的 Public Hostname 会覆盖本地 `config.yml` 的 ingress。当前 Dashboard 指向 `http://localhost:88`，与 `network_mode: service:allahpan-nginx` 配合可正常工作。

**推荐后续优化**（可选）：在 [Cloudflare Zero Trust](https://one.dash.cloudflare.com) → Networks → Connectors → Cloudflare Tunnels → `Allahpan-win` → Public Hostname 中，删除 Dashboard 规则改由本地 `config.yml` 管理，或将 origin 改为 `http://127.0.0.1:88`。同时确认无 `--protocol http2` 远程 run 参数。

## 验证

```powershell
docker logs allahpan-cloudflared --tail 20
# 应看到 4 条 Registered tunnel connection

& "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel info 34641e20-8826-4545-bf00-df32c69a7cfb
# EDGE 列应显示 4 个 location

curl https://allahpan.cn
```

## 日志与指标

- 容器日志：`docker compose logs -f cloudflared`
- Prometheus metrics：`http://localhost:20241/metrics`
