# 15分ごとに API/UI/トンネルを監視し、落ちていれば自動復旧
# install-stable.ps1 からタスク登録
param(
    [ValidateSet("lan", "tunnel", "both", "local")]
    [string]$Mode = "both"
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
Set-Location $Root
. (Join-Path $Root "scripts\helix-core.ps1")

$dataDir = Join-Path $Root "data"
$null = New-Item -ItemType Directory -Force -Path $dataDir
$logFile = Join-Path $dataDir "watchdog.log"

function Write-WatchLog {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $logFile -Value $line -Encoding UTF8
}

. (Join-Path $Root "scripts\helix-core.ps1")
$health = Test-HelixStackHealthy -Root $Root -CheckTunnel:($Mode -in @("tunnel", "both"))

if ($health.Ok) {
    Write-WatchLog "OK api=$($health.Api) ui=$($health.Ui) tunnel=$($health.Tunnel)"
    exit 0
}

Write-WatchLog "UNHEALTHY api=$($health.Api) ui=$($health.Ui) tunnel=$($health.Tunnel) — repair"
& (Join-Path $Root "scripts\helix-autostart.ps1") -Mode $Mode -SkipCollector -RepairOnly

$after = Test-HelixStackHealthy -Root $Root -CheckTunnel:($Mode -in @("tunnel", "both"))
Write-WatchLog "After repair api=$($after.Api) ui=$($after.Ui) tunnel=$($after.Tunnel) ok=$($after.Ok)"
if (-not $after.Ok) { exit 1 }
exit 0
