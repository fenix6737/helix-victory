# 長時間稼働の健全性チェック（メモリ・プロセス・API）
param(
    [string]$Root = (Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent),
    [switch]$Fix
)

. (Join-Path $Root "scripts\helix-core.ps1")

function Test-CollectorRunning {
    return (@(Get-HelixCollectorProcesses).Count -gt 0)
}

if ($Fix) {
    Remove-StaleHelixProcesses -Root $Root -Log { Write-Host $_ }
    if (-not (Test-CollectorRunning)) {
        & (Join-Path $Root "scripts\helix-autostart.ps1") -Mode local -SkipTunnel 2>&1 | Out-Null
        Start-Sleep -Seconds 2
        Remove-DuplicateCollectors -Log { Write-Host $_ }
    }
}

$report = @()
function Add($name, $ok, $detail) { $script:report += [pscustomobject]@{ Check = $name; OK = $ok; Detail = $detail } }

$health = Test-HelixStackHealthy -Root $Root -CheckTunnel
Add "Stack" $health.Ok "api=$($health.Api) ui=$($health.Ui) tunnel=$($health.Tunnel)"

$collectors = @(Get-HelixCollectorProcesses)
Add "Collector count" ($collectors.Count -eq 1) "count=$($collectors.Count) (want 1)"

$cf = @(Get-Process cloudflared -EA SilentlyContinue)
Add "Cloudflared count" ($cf.Count -le 1) "count=$($cf.Count)"

$port3000 = @(Get-NetTCPConnection -LocalPort 3000 -State Listen -EA SilentlyContinue | Select-Object -Expand OwningProcess -Unique)
Add "Frontend listeners" ($port3000.Count -le 2) "pids=$($port3000 -join ',')"

$analysisProcs = @(Get-HelixAnalysisLoopProcesses)
$analysisOk = $analysisProcs.Count -ge 1
Add "Analysis loop" $analysisOk $(if ($analysisOk) { "pid $($analysisProcs[0].ProcessId)" } else { "not running — run Start Helix Victory.bat or autostart" })

$pyMem = (Get-Process python -EA SilentlyContinue | Measure-Object -Property WS -Sum).Sum / 1MB
$nodeMem = (Get-Process node -EA SilentlyContinue | Measure-Object -Property WS -Sum).Sum / 1MB
Add "Memory python" ($pyMem -lt 800) "${pyMem}MB total"
Add "Memory node" ($nodeMem -lt 1200) "${nodeMem}MB total"

$db = Join-Path $Root "backend\helix_local.db"
if (Test-Path $db) {
    $dbMb = (Get-Item $db).Length / 1MB
    Add "SQLite size" ($dbMb -lt 2048) "${dbMb}MB"
}

Write-Host ""
Write-Host "=== Long-run audit ===" -ForegroundColor Cyan
$fail = 0
foreach ($r in $report) {
    $c = if ($r.OK) { "Green" } else { "Red"; $fail++ }
    Write-Host ("[{0}] {1} — {2}" -f $(if ($r.OK) { "OK" } else { "NG" }), $r.Check, $r.Detail) -ForegroundColor $c
}
Write-Host ""
if ($fail -eq 0) { exit 0 }
exit 1
