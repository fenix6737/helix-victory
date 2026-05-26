# 週次再発防止確認タスク（日曜 03:00）
param([string]$Root = (Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent))

$scriptPath = Join-Path $Root "scripts\verify-recurrence-prevention.ps1"
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`" -Phase weekly -RequireSoakPass -RequireLoadPass" `
    -WorkingDirectory $Root
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 3am
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName "HelixVictoryRecurrenceCheck" -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description "Weekly stability recurrence prevention checks" -Force | Out-Null
Write-Host "Registered: HelixVictoryRecurrenceCheck (Sunday 03:00)"
