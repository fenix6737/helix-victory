# 実行中または直近のソークテスト状況
param([string]$Root = (Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent))

$dataDir = Join-Path $Root "data"
$progress = Join-Path $dataDir "soak-progress.jsonl"
$latest = Get-ChildItem (Join-Path $dataDir "soak-report-*.json") -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1

Write-Host "=== Soak status ===" -ForegroundColor Cyan
if (Test-Path $progress) {
    $last = Get-Content $progress -Tail 1 | ConvertFrom-Json
    Write-Host ("Last sample: ts={0} n={1} api={2} ui={3} tunnel={4}" -f $last.ts, $last.sample, $last.api, $last.ui, $last.tunnel)
    Write-Host ("Progress lines: {0}" -f (Get-Content $progress).Count)
} else {
    Write-Host "No soak-progress.jsonl yet"
}
if ($latest) {
    $r = Get-Content $latest.FullName -Raw | ConvertFrom-Json
    Write-Host ("Latest report: {0} pass={1} ui={2}% api={3}%" -f $latest.Name, $r.pass, $r.success_rate.ui_pct, $r.success_rate.api_pct)
} else {
    Write-Host "No soak-report yet"
}
Get-Content (Join-Path $dataDir "soak-run.log") -Tail 5 -ErrorAction SilentlyContinue
