# Windows ログオン時に Helix Victory を自動起動するタスクを登録
# 管理者で実行推奨（ファイアウォールは別途）
# Usage: .\scripts\install-autostart.ps1
# Remove: .\scripts\uninstall-autostart.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
$taskName = "HelixVictoryAutoStart"
$scriptPath = Join-Path $Root "scripts\helix-autostart.ps1"

if (-not (Test-Path $scriptPath)) {
    Write-Error "Not found: $scriptPath"
    exit 1
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$scriptPath`"" `
    -WorkingDirectory $Root

# ログオン後 30 秒（ネットワーク・PATH の準備待ち）
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$trigger.Delay = "PT30S"

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Helix Victory: API + UI + collector + Cloudflare tunnel on logon" | Out-Null

Write-Host "Registered scheduled task: $taskName" -ForegroundColor Green
Write-Host "  Runs at logon (~30s delay)"
Write-Host "  Log: $Root\data\autostart.log"
Write-Host "  URLs: $Root\data\public-url.txt"
Write-Host "  Desktop: Helix Victory (公開).url  (起動のたびに更新)"
Write-Host ""
Write-Host "手動起動（URLをダイアログ表示）:" -ForegroundColor Cyan
Write-Host "  $Root\Start Helix Victory.bat"
Write-Host ""
Write-Host "Test now:" -ForegroundColor Cyan
Write-Host "  .\scripts\install-stable.ps1   # autostart + 15min watchdog (recommended)"
Write-Host "  Start-ScheduledTask -TaskName $taskName"
Write-Host "  Get-Content $Root\data\autostart.log -Tail 20 -Wait"
