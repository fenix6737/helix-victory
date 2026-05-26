# 1分ごとの安定性メトリクスを data/metrics.csv に追記（スーパーバイザーから呼ぶ）
param(
    [string]$Root = (Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent)
)

. (Join-Path $Root "scripts\helix-core.ps1")

$dataDir = Join-Path $Root "data"
$csv = Join-Path $dataDir "metrics.csv"
$null = New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

$ts = (Get-Date).ToString("o")
$health = Test-HelixStackHealthy -Root $Root -CheckTunnel

$py = Get-Process python -EA SilentlyContinue
$node = Get-Process node -EA SilentlyContinue
$cf = @(Get-Process cloudflared -EA SilentlyContinue).Count
$pyMb = if ($py) { [math]::Round(($py | Measure-Object WS -Sum).Sum / 1MB, 2) } else { 0 }
$nodeMb = if ($node) { [math]::Round(($node | Measure-Object WS -Sum).Sum / 1MB, 2) } else { 0 }

$cpuPy = if ($py) { [math]::Round(($py | Measure-Object CPU -Sum).Sum, 2) } else { 0 }
$cpuNode = if ($node) { [math]::Round(($node | Measure-Object CPU -Sum).Sum, 2) } else { 0 }

$listen8000 = @(Get-NetTCPConnection -LocalPort 8000 -State Listen -EA SilentlyContinue).Count
$listen3000 = @(Get-NetTCPConnection -LocalPort 3000 -State Listen -EA SilentlyContinue).Count
$collectors = @(Get-HelixCollectorProcesses).Count

$row = [PSCustomObject]@{
    timestamp_utc     = $ts
    api_ok            = $health.Api
    ui_ok             = $health.Ui
    tunnel_ok         = $health.Tunnel
    py_mb             = $pyMb
    node_mb           = $nodeMb
    py_cpu_sec        = $cpuPy
    node_cpu_sec      = $cpuNode
    cloudflared_count = $cf
    collector_count   = $collectors
    listen_8000       = $listen8000
    listen_3000       = $listen3000
}

if (-not (Test-Path $csv)) {
    $row | Export-Csv -Path $csv -NoTypeInformation -Encoding UTF8
} else {
    $row | Export-Csv -Path $csv -NoTypeInformation -Encoding UTF8 -Append
}
