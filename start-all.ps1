# ============================================================
# AllahPan 一键启动脚本
# 首次运行: .\start-all.ps1 -Build
# 快速重启: .\start-all.ps1
# ============================================================
param([switch]$Build)

Write-Host "╔══════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     AllahPan — 容器化部署启动        ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════╝" -ForegroundColor Cyan

if ($Build) {
    Write-Host "`n[1/3] 本地编译后端 JAR..." -ForegroundColor Yellow
    mvn package -DskipTests -q
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  编译失败！请检查 Maven 配置" -ForegroundColor Red
        exit 1
    }
    Write-Host "  编译完成" -ForegroundColor Green
}

Write-Host "`n[2/3] 构建镜像 + 启动容器..." -ForegroundColor Yellow
docker-compose up -d --build
if ($LASTEXITCODE -ne 0) {
    Write-Host "  启动失败！" -ForegroundColor Red
    exit 1
}

Write-Host "`n[3/3] 等待服务就绪..." -ForegroundColor Yellow
Start-Sleep 15

# 健康检查
Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  服务状态" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray

$services = @(
    @{Name="核心 API";     URL="http://localhost:8088/api/file/list"},
    @{Name="搜索服务";     URL="http://localhost:8081"},
    @{Name="前端页面";     URL="http://localhost:88"}
)

foreach ($svc in $services) {
    try {
        $code = (Invoke-WebRequest -Uri $svc.URL -UseBasicParsing -TimeoutSec 5).StatusCode
        Write-Host "  ✓ $($svc.Name) — $($svc.URL) [$code]" -ForegroundColor Green
    } catch {
        Write-Host "  ✗ $($svc.Name) — $($svc.URL) [启动中...]" -ForegroundColor Yellow
    }
}

# Cloudflare Tunnel 健康检查
$tunnelLogs = docker logs allahpan-cloudflared --tail 30 2>&1 | Out-String
$tunnelConnections = ([regex]::Matches($tunnelLogs, "Registered tunnel connection")).Count
if ($tunnelConnections -ge 1) {
    Write-Host "  ✓ Cloudflare Tunnel — $tunnelConnections 条边缘连接已注册" -ForegroundColor Green
} else {
    Write-Host "  ✗ Cloudflare Tunnel — 未检测到连接，查看: docker compose logs cloudflared" -ForegroundColor Yellow
}

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  访问地址" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  本地     : http://localhost:88"           -ForegroundColor White
Write-Host "  公网     : https://allahpan.cn"            -ForegroundColor Green
Write-Host "  MinIO    : http://localhost:9001 (minioadmin/minioadmin)" -ForegroundColor Gray
Write-Host "  RabbitMQ : http://localhost:15672 (guest/guest)" -ForegroundColor Gray
Write-Host "`n  隧道日志 : docker compose logs -f cloudflared" -ForegroundColor Gray
