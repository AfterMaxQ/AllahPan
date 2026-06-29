# DEPRECATED — 请改用 .\start-all.ps1
# 旧版混合部署（宿主机 JAR + 外部 nginx + Windows cloudflared）已废弃。
# 生产环境统一使用 Docker Compose，含 allahpan-cloudflared 容器。
Write-Host "start-prod.ps1 已废弃，正在转发到 start-all.ps1 ..." -ForegroundColor Yellow
& "$PSScriptRoot\start-all.ps1" @args
