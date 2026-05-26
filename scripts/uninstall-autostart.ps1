# Helix Victory 自動起動タスクを削除
$tasks = @("HelixVictoryAutoStart", "HelixVictoryWatchdog", "HelixVictorySupervisor")
foreach ($taskName in $tasks) {
    $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Write-Host "Removed: $taskName" -ForegroundColor Green
    } else {
        Write-Host "Task not found: $taskName"
    }
}
