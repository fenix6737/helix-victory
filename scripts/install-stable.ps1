# 常時安定 — 本番UIビルド + 常駐スーパーバイザー（60秒監視）
# Usage: .\scripts\install-stable.ps1
# Remove: .\scripts\uninstall-autostart.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
$feDir = Join-Path $Root "frontend"

Write-Host "Helix Victory stable mode installer" -ForegroundColor Cyan
Write-Host ""

Write-Host "Building frontend (standard mode for Windows stability)..." -ForegroundColor Yellow
Push-Location $feDir
try {
    if (-not (Test-Path "node_modules")) {
        npm ci 2>&1 | Out-Host
    }
    if (Test-Path ".next") { Remove-Item ".next" -Recurse -Force -ErrorAction SilentlyContinue }
    npm run build 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Frontend build failed — autostart will use dev:public" -ForegroundColor Red
    } else {
        Set-Content -Path (Join-Path $Root "data\stable-ui.flag") -Value "production" -Encoding UTF8
        Write-Host "Frontend build OK — autostart will use start:public" -ForegroundColor Green
    }
} finally {
    Pop-Location
}

$supervisorScript = Join-Path $Root "scripts\helix-supervisor.ps1"
$superTask = "HelixVictorySupervisor"

# 旧タスクを削除（重複起動防止）
foreach ($old in @("HelixVictoryAutoStart", "HelixVictoryWatchdog")) {
    $existing = Get-ScheduledTask -TaskName $old -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $old -Confirm:$false
        Write-Host "Removed old task: $old"
    }
}

$superAction = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$supervisorScript`"" `
    -WorkingDirectory $Root

$superTrigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$superTrigger.Delay = "PT45S"

$superSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1)

$superPrincipal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
    -TaskName $superTask `
    -Action $superAction `
    -Trigger $superTrigger `
    -Settings $superSettings `
    -Principal $superPrincipal `
    -Description "Helix Victory: supervisor loop — auto start + repair every 60s" | Out-Null

Write-Host ""
Write-Host "Registered supervisor task: $superTask" -ForegroundColor Green
Write-Host "  Logon +45s, then health check every 60s"
Write-Host "  Logs: data/supervisor.log, data/autostart.log"
Write-Host ""
Write-Host "Stable mode:" -ForegroundColor Green
Write-Host "  - SQLite API (no Postgres wait on boot)"
Write-Host "  - Production Next.js when built"
Write-Host "  - 3x retry on boot + lock against duplicate starts"
Write-Host "  - Auto-repair API / UI / tunnel while PC is on"
Write-Host ""
Write-Host "Manual start with URL dialog:" -ForegroundColor Cyan
Write-Host "  $Root\Start Helix Victory.bat"
Write-Host ""
Write-Host "Verify now:" -ForegroundColor Cyan
Write-Host "  Start-ScheduledTask -TaskName $superTask"
