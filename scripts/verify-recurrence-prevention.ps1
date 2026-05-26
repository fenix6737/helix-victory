# 再発防止確認 — チェック結果を data/recurrence-prevention.jsonl に追記
param(
    [string]$Root = (Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent),
    [switch]$RequireSoakPass,
    [switch]$RequireLoadPass,
    [string]$Phase = "manual"
)

. (Join-Path $Root "scripts\helix-core.ps1")

$dataDir = Join-Path $Root "data"
$logPath = Join-Path $dataDir "recurrence-prevention.jsonl"
$null = New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

$checks = @()
function Add-Check($name, $ok, $detail) {
    $script:checks += [PSCustomObject]@{ name = $name; ok = $ok; detail = $detail }
}

# 1. 本番UIビルド
$buildId = Join-Path $Root "frontend\.next\BUILD_ID"
Add-Check "frontend_build_id" (Test-Path $buildId) $(if (Test-Path $buildId) { "present" } else { "missing — run install-stable.ps1" })

# 2. 常駐が dev でない（ログ末尾）
$feLog = Join-Path $dataDir "frontend.log"
$devInLog = $false
$prodInLog = $false
if (Test-Path $feLog) {
    $tail = Get-Content $feLog -Tail 80 -ErrorAction SilentlyContinue
    $devInLog = $null -ne ($tail | Select-String "dev:public|next dev" | Select-Object -Last 1)
    $prodInLog = $null -ne ($tail | Select-String "start:public|next start" | Select-Object -Last 1)
}
Add-Check "frontend_not_dev_mode_recent" (-not $devInLog -or $prodInLog) "dev_in_tail=$devInLog prod_in_tail=$prodInLog"

# 3. メトリクスCSV
$metrics = Join-Path $dataDir "metrics.csv"
$metricRows = 0
if (Test-Path $metrics) {
    $metricRows = (Import-Csv $metrics).Count
}
Add-Check "metrics_csv_exists" ($metricRows -ge 1) "rows=$metricRows"

# 4. スーパーバイザータスク
$superTask = Get-ScheduledTask -TaskName "HelixVictorySupervisor" -ErrorAction SilentlyContinue
Add-Check "supervisor_task_registered" ($null -ne $superTask) $(if ($superTask) { [string]$superTask.State } else { "missing" })

# 5. 単一 collector / cloudflared
Add-Check "single_collector" ((@(Get-HelixCollectorProcesses).Count) -eq 1) "count=$((@(Get-HelixCollectorProcesses).Count))"
Add-Check "single_cloudflared" ((@(Get-Process cloudflared -EA SilentlyContinue).Count) -le 1) "count=$((@(Get-Process cloudflared -EA SilentlyContinue).Count))"

# 6. 分析ループ常駐
Add-Check "analysis_loop_running" ((@(Get-HelixAnalysisLoopProcesses).Count) -ge 1) "count=$((@(Get-HelixAnalysisLoopProcesses).Count))"

# 7. 直近ソーク合格
$soakPass = $false
$soakReport = Get-ChildItem (Join-Path $dataDir "soak-report-*.json") -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($soakReport) {
    try {
        $sr = Get-Content $soakReport.FullName -Raw | ConvertFrom-Json
        $soakPass = [bool]$sr.pass
        Add-Check "latest_soak_report" $soakPass "$($soakReport.Name) ui=$($sr.success_rate.ui_pct)% api=$($sr.success_rate.api_pct)%"
    } catch {
        Add-Check "latest_soak_report" $false "parse error"
    }
} else {
    Add-Check "latest_soak_report" (-not $RequireSoakPass) "no soak-report yet"
}

# 8. 直近負荷試験合格
$loadPass = $false
$loadReport = Get-ChildItem (Join-Path $dataDir "load-report-*.json") -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($loadReport) {
    try {
        $lr = Get-Content $loadReport.FullName -Raw | ConvertFrom-Json
        $loadPass = [bool]$lr.pass
        Add-Check "latest_load_report" $loadPass $loadReport.Name
    } catch {
        Add-Check "latest_load_report" $false "parse error"
    }
} else {
    Add-Check "latest_load_report" (-not $RequireLoadPass) "no load-report yet"
}

# 9. スタック健全
$health = Test-HelixStackHealthy -Root $Root -CheckTunnel
Add-Check "stack_healthy_now" $health.Ok "api=$($health.Api) ui=$($health.Ui) tunnel=$($health.Tunnel)"

# 10. インシデント報告書存在
Add-Check "incident_report_exists" (Test-Path (Join-Path $Root "docs\INCIDENT_STABILITY_REPORT.md")) "docs/INCIDENT_STABILITY_REPORT.md"

$fail = @($checks | Where-Object { -not $_.ok }).Count
$entry = @{
    ts      = (Get-Date).ToString("o")
    phase   = $Phase
    pass    = ($fail -eq 0)
    failed  = $fail
    checks  = $checks
} | ConvertTo-Json -Depth 5 -Compress

Add-Content -Path $logPath -Value $entry -Encoding UTF8

Write-Host ""
Write-Host "=== Recurrence prevention ($Phase) ===" -ForegroundColor Cyan
foreach ($c in $checks) {
    $col = if ($c.ok) { "Green" } else { "Red" }
    Write-Host ("[{0}] {1} — {2}" -f $(if ($c.ok) { "OK" } else { "NG" }), $c.name, $c.detail) -ForegroundColor $col
}
Write-Host "Log: $logPath"
if ($fail -eq 0) { exit 0 }
exit 1
