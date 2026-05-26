# 毎日 00:05 JST 相当 — 日次学習サイクル（PC常時起動時）
param([string]$Root = (Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent))

$scriptPath = Join-Path $Root "scripts\midnight-daily-cycle.ps1"
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$scriptPath`"" `
    -WorkingDirectory $Root
$trigger = New-ScheduledTaskTrigger -Daily -At "00:05"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName "HelixVictoryMidnightCycle" -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description "Daily prediction learning cycle after midnight" -Force | Out-Null
Write-Host "Registered: HelixVictoryMidnightCycle (daily 00:05)"
