# Cloudflare Tunnel health check
# Usage: .\scripts\tunnel-health.ps1
param(
    [switch]$Quiet
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Log($msg, $color = "White") {
    if (-not $Quiet) { Write-Host $msg -ForegroundColor $color }
}

$healthy = $true

$status = docker inspect allahpan-cloudflared --format '{{.State.Status}}' 2>$null
if ($status -ne "running") {
    Log "cloudflared container not running (status=$status), restarting..." "Yellow"
    docker compose restart cloudflared 2>&1 | Out-Null
    $healthy = $false
} else {
    Log "cloudflared container: running" "Green"
}

$tunnelLogs = docker logs allahpan-cloudflared --tail 50 2>&1 | Out-String
$connections = ([regex]::Matches($tunnelLogs, "Registered tunnel connection")).Count
if ($connections -lt 2) {
    Log "Tunnel connections low ($connections/4), restarting cloudflared..." "Yellow"
    docker compose restart cloudflared 2>&1 | Out-Null
    $healthy = $false
} else {
    Log "Tunnel connections: $connections registered" "Green"
}

try {
    $resp = Invoke-WebRequest -Uri "https://allahpan.cn" -UseBasicParsing -TimeoutSec 10
    if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 400) {
        Log "Public https://allahpan.cn : HTTP $($resp.StatusCode)" "Green"
    } else {
        Log "Public response abnormal: HTTP $($resp.StatusCode)" "Yellow"
        $healthy = $false
    }
} catch {
    Log "Public unreachable: $($_.Exception.Message)" "Red"
    docker compose restart cloudflared 2>&1 | Out-Null
    $healthy = $false
}

if (-not $healthy) {
    Log "Health check failed, attempted cloudflared restart" "Yellow"
    exit 1
}

Log "Health check passed" "Green"
exit 0
