# AllahPan Production Startup Script
# Run this to start all services for https://allahpan.cn
$ErrorActionPreference = "Continue"
$Root = "F:\Java\allahpan"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AllahPan Production Startup"           -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 0. Set production profile
$env:SPRING_PROFILES_ACTIVE = "prod"

# 1. Check Docker infrastructure
Write-Host "`n[0/5] Checking Docker infrastructure..." -ForegroundColor Yellow
$running = docker ps --format "{{.Names}}" 2>$null
if (-not $running) {
    Write-Host "       Docker is not running or no containers. Start Docker Desktop and run:" -ForegroundColor Red
    Write-Host "       cd $Root && docker compose up -d" -ForegroundColor Red
    exit 1
}
$required = @("mysql-allahpan", "redis-allahpan", "rabbitmq", "elasticsearch-allahpan", "minio")
$missing = $required | Where-Object { $_ -notin $running }
if ($missing) {
    Write-Host "       Missing containers: $($missing -join ', ')" -ForegroundColor Red
    Write-Host "       Run: docker compose up -d" -ForegroundColor Red
    exit 1
}
Write-Host "       All 5 Docker containers running." -ForegroundColor Green

# 2. Start search service (port 8081, internal only)
Write-Host "`n[1/5] Starting Search Service (port 8081)..." -ForegroundColor Yellow
$searchJar = "$Root\allahpan-search\target\allahpan-search-1.0.0.jar"
if (-not (Test-Path $searchJar)) {
    Write-Host "       JAR not found, building..." -ForegroundColor Yellow
    mvn package -DskipTests -pl allahpan-search -am -q
}
$searchJob = Start-Job -ScriptBlock {
    param($jar)
    java -jar "-Dspring.profiles.active=prod" $jar 2>&1
} -ArgumentList $searchJar
Write-Host "       Search service starting (PID background job)..." -ForegroundColor Green

# Wait for search service to be ready
for ($i = 1; $i -le 30; $i++) {
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:8081/es-admin/files/search?keyword=__health__&pageNum=1&pageSize=1" -TimeoutSec 2 -UseBasicParsing
        Write-Host "       Search service ready." -ForegroundColor Green
        break
    } catch {
        if ($i -eq 30) {
            Write-Host "       WARNING: Search service not responding after 60s" -ForegroundColor Red
        }
    }
    Start-Sleep -Seconds 2
}

# 3. Start core service (port 8088)
Write-Host "`n[2/5] Starting Core Service (port 8088)..." -ForegroundColor Yellow
$coreJar = "$Root\allahpan-core\target\allahpan-core-1.0.0.jar"
if (-not (Test-Path $coreJar)) {
    Write-Host "       JAR not found, building..." -ForegroundColor Yellow
    mvn package -DskipTests -q
}
$coreJob = Start-Job -ScriptBlock {
    param($jar)
    java -jar "-Dspring.profiles.active=prod" $jar 2>&1
} -ArgumentList $coreJar
Write-Host "       Core service starting (PID background job)..." -ForegroundColor Green

# Wait for core service to be ready
for ($i = 1; $i -le 45; $i++) {
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:8088/error" -TimeoutSec 2 -UseBasicParsing
        Write-Host "       Core service ready." -ForegroundColor Green
        break
    } catch {
        if ($_.Exception.Response.StatusCode -eq 404) {
            Write-Host "       Core service ready (HTTP 404 on /error is expected)." -ForegroundColor Green
            break
        }
        if ($i -eq 45) {
            Write-Host "       WARNING: Core service not responding after 90s" -ForegroundColor Red
        }
    }
    Start-Sleep -Seconds 2
}

# 4. Start nginx (port 88)
Write-Host "`n[3/5] Starting nginx (port 88)..." -ForegroundColor Yellow
$nginxExe = "C:\nginx-1.26.3\nginx.exe"
if (-not (Test-Path $nginxExe)) {
    Write-Host "       nginx not found at $nginxExe" -ForegroundColor Red
    exit 1
}
# Reload if already running, start if not
$nginxRunning = Get-Process -Name nginx -ErrorAction SilentlyContinue
if ($nginxRunning) {
    Write-Host "       nginx already running, reloading config..." -ForegroundColor Yellow
    Set-Location C:\nginx-1.26.3
    .\nginx.exe -s reload
} else {
    Set-Location C:\nginx-1.26.3
    Start-Process .\nginx.exe -WindowStyle Hidden
    Write-Host "       nginx started." -ForegroundColor Green
}

# 5. Verify cloudflared
Write-Host "`n[4/5] Checking cloudflared tunnel..." -ForegroundColor Yellow
$cf = Get-Service cloudflared -ErrorAction SilentlyContinue
if ($cf.Status -eq "Running") {
    Write-Host "       cloudflared is running." -ForegroundColor Green
    Write-Host "       NOTE: If you changed config.yml, restart with admin: Restart-Service cloudflared" -ForegroundColor Yellow
} else {
    Write-Host "       cloudflared is NOT running. Start with:" -ForegroundColor Red
    Write-Host "       net start cloudflared (requires admin)" -ForegroundColor Red
}

# Done
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  AllahPan is running!"                   -ForegroundColor Cyan
Write-Host "  Local:    http://localhost:88"          -ForegroundColor White
Write-Host "  Public:   https://allahpan.cn"          -ForegroundColor White
Write-Host "  API:      https://api.allahpan.cn"      -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "`nTo stop services:" -ForegroundColor Yellow
Write-Host "  Get-Job | Stop-Job" -ForegroundColor White
Write-Host "  C:\nginx-1.26.3\nginx.exe -s quit" -ForegroundColor White
Write-Host "`nTo view logs:" -ForegroundColor Yellow
Write-Host "  Receive-Job -Id $($searchJob.Id)  # Search service" -ForegroundColor White
Write-Host "  Receive-Job -Id $($coreJob.Id)    # Core service" -ForegroundColor White
