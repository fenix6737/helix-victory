# 負荷試験 — 同時リクエストで API/UI の失敗率・レイテンシを計測
param(
    [string]$Root = (Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent),
    [int]$Concurrent = 10,
    [int]$RequestsPerWorker = 15,
    [int]$TimeoutSec = 15,
    [string]$ReportPath = ""
)

$ErrorActionPreference = "Continue"
$dataDir = Join-Path $Root "data"
$null = New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
if (-not $ReportPath) {
    $ReportPath = Join-Path $dataDir ("load-report-{0}.json" -f (Get-Date -Format "yyyyMMdd-HHmmss"))
}

$targets = @(
    @{ name = "api_health"; url = "http://127.0.0.1:8000/health" },
    @{ name = "ui_welcome"; url = "http://127.0.0.1:3000/welcome" },
    @{ name = "api_combat"; url = "http://127.0.0.1:8000/health/combat" }
)

$started = Get-Date
Write-Host "Load test: $Concurrent workers x $($RequestsPerWorker) req -> $ReportPath" -ForegroundColor Cyan

$allResults = [System.Collections.Concurrent.ConcurrentBag[object]]::new()

$jobs = @()
foreach ($t in $targets) {
    for ($w = 0; $w -lt $Concurrent; $w++) {
        $jobs += Start-Job -ScriptBlock {
            param($name, $url, $n, $timeout)
            $out = @()
            for ($i = 0; $i -lt $n; $i++) {
                $sw = [System.Diagnostics.Stopwatch]::StartNew()
                $code = "000"
                try {
                    $code = curl.exe -s -o NUL -w "%{http_code}" --max-time $timeout $url 2>$null
                } catch { }
                $sw.Stop()
                $out += [PSCustomObject]@{
                    target = $name
                    http   = $code
                    ms     = [math]::Round($sw.Elapsed.TotalMilliseconds, 1)
                    ok     = ($code -eq "200")
                }
            }
            return $out
        } -ArgumentList $t.name, $t.url, $RequestsPerWorker, $TimeoutSec
    }
}

Wait-Job $jobs | Out-Null
foreach ($j in $jobs) {
    Receive-Job $j | ForEach-Object { $allResults.Add($_) }
    Remove-Job $j -Force
}

$byTarget = $allResults | Group-Object target
$summary = @{}
$pass = $true
foreach ($g in $byTarget) {
    $arr = @($g.Group)
    $total = $arr.Count
    $ok = @($arr | Where-Object { $_.ok }).Count
    $pct = if ($total) { [math]::Round(100 * $ok / $total, 2) } else { 0 }
    $ms = @($arr | Where-Object { $_.ok } | ForEach-Object { [double]$_.ms })
    $p95 = if ($ms.Count) {
        $sorted = $ms | Sort-Object
        $idx = [math]::Min($sorted.Count - 1, [math]::Ceiling($sorted.Count * 0.95) - 1)
        $sorted[[math]::Max(0, $idx)]
    } else { 0 }
    $summary[$g.Name] = @{
        total       = $total
        ok          = $ok
        fail        = $total - $ok
        success_pct = $pct
        p95_ms      = $p95
    }
    if ($pct -lt 99) { $pass = $false }
}

$report = @{
    started_at       = $started.ToString("o")
    finished_at      = (Get-Date).ToString("o")
    concurrent       = $Concurrent
    requests_per_worker = $RequestsPerWorker
    total_requests   = $allResults.Count
    targets          = $summary
    pass             = $pass
    slo              = "each target success_pct >= 99"
}
$report | ConvertTo-Json -Depth 6 | Set-Content -Path $ReportPath -Encoding UTF8

Write-Host ""
Write-Host "=== Load test result ===" -ForegroundColor Cyan
foreach ($k in $summary.Keys) {
    $s = $summary[$k]
    Write-Host ("{0}: {1}% ok ({2}/{3}) p95={4}ms" -f $k, $s.success_pct, $s.ok, $s.total, $s.p95_ms)
}
Write-Host "Report: $ReportPath"
if ($pass) {
    Write-Host "PASS" -ForegroundColor Green
    exit 0
}
Write-Host "FAIL" -ForegroundColor Red
exit 1
