# 長時間ソークテスト — API/UI/トンネルの成功率を時系列で記録
param(
    [string]$Root = (Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent),
    [double]$Hours = 3,
    [int]$IntervalSec = 60,
    [string]$ReportPath = ""
)

. (Join-Path $Root "scripts\helix-core.ps1")

$dataDir = Join-Path $Root "data"
$progressLog = Join-Path $dataDir "soak-progress.jsonl"
$null = New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
if (-not $ReportPath) {
    $ReportPath = Join-Path $dataDir ("soak-report-{0}.json" -f (Get-Date -Format "yyyyMMdd-HHmmss"))
}

$probes = @(
    @{ name = "api_health"; url = "http://127.0.0.1:8000/health" },
    @{ name = "ui_welcome"; url = "http://127.0.0.1:3000/welcome" }
)

$started = Get-Date
$end = $started.AddHours($Hours)
$samples = New-Object System.Collections.Generic.List[object]
$ok = @{ api = 0; ui = 0; tunnel = 0; total = 0 }

Write-Host "Soak test: $Hours h, interval ${IntervalSec}s -> $ReportPath" -ForegroundColor Cyan

while ((Get-Date) -lt $end) {
    $ok.total++
    $row = @{ ts = (Get-Date).ToString("o"); probes = @{} }
    foreach ($p in $probes) {
        $code = "000"
        $ms = 0
        try {
            $ms = [math]::Round((Measure-Command {
                $code = curl.exe -s -o NUL -w "%{http_code}" --max-time 12 $p.url 2>$null
            }).TotalMilliseconds, 1)
        } catch { }
        $pass = $code -eq "200"
        $row.probes[$p.name] = @{ http = $code; ms = $ms; ok = $pass }
        if ($p.name -eq "api_health" -and $pass) { $ok.api++ }
        if ($p.name -eq "ui_welcome" -and $pass) { $ok.ui++ }
    }
    $h = Test-HelixStackHealthy -Root $Root -CheckTunnel
    $row.tunnel_ok = $h.Tunnel
    if ($h.Tunnel) { $ok.tunnel++ }
    $samples.Add($row) | Out-Null
    $progress = @{
        ts = $row.ts
        api = $row.probes["api_health"].ok
        ui = $row.probes["ui_welcome"].ok
        tunnel = $row.tunnel_ok
        sample = $ok.total
    } | ConvertTo-Json -Compress
    Add-Content -Path $progressLog -Value $progress -Encoding UTF8
    & (Join-Path $Root "scripts\stability-metrics.ps1") -Root $Root
    if ($ok.total % 10 -eq 0) {
        Write-Host ("[{0}] sample={1} api_ok={2} ui_ok={3}" -f (Get-Date -Format "HH:mm:ss"), $ok.total, $ok.api, $ok.ui)
    }
    Start-Sleep -Seconds $IntervalSec
}

$rate = @{
    api_pct    = if ($ok.total) { [math]::Round(100 * $ok.api / $ok.total, 2) } else { 0 }
    ui_pct     = if ($ok.total) { [math]::Round(100 * $ok.ui / $ok.total, 2) } else { 0 }
    tunnel_pct = if ($ok.total) { [math]::Round(100 * $ok.tunnel / $ok.total, 2) } else { 0 }
}
$report = @{
    started_at   = $started.ToString("o")
    finished_at  = (Get-Date).ToString("o")
    hours        = $Hours
    interval_sec = $IntervalSec
    samples      = $ok.total
    success_rate = $rate
    pass         = ($rate.ui_pct -ge 99 -and $rate.api_pct -ge 99)
    note         = "tunnel_pct is informational for trycloudflare; UI/API are primary SLO"
}
$report | ConvertTo-Json -Depth 6 | Set-Content -Path $ReportPath -Encoding UTF8

Write-Host ""
Write-Host "=== Soak result ===" -ForegroundColor Cyan
Write-Host ("API: {0}%  UI: {1}%  Tunnel: {2}%  samples={3}" -f $rate.api_pct, $rate.ui_pct, $rate.tunnel_pct, $ok.total)
Write-Host ("Report: {0}" -f $ReportPath)
$gateLog = Join-Path $dataDir "release-gate.log"
Add-Content -Path $gateLog -Value ("[{0}] soak finished pass={1} ui={2}% api={3}%" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $report.pass, $rate.ui_pct, $rate.api_pct) -Encoding UTF8

if ($report.pass) {
    Write-Host "PASS (UI/API >= 99%)" -ForegroundColor Green
    & (Join-Path $Root "scripts\verify-recurrence-prevention.ps1") -Root $Root -Phase "post-soak" -RequireSoakPass -RequireLoadPass
    exit $LASTEXITCODE
}
Write-Host "FAIL (UI/API < 99%)" -ForegroundColor Red
& (Join-Path $Root "scripts\verify-recurrence-prevention.ps1") -Root $Root -Phase "post-soak-fail"
exit 1
