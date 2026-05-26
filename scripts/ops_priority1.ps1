# Helix Victory — 最優先運用: API再起動 → ingest → 検証
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent

Write-Host "=== [1/4] Stop process on port 8000 ===" -ForegroundColor Cyan
$pids = @(Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
foreach ($procId in $pids) {
    if ($procId -and $procId -ne 0) {
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        Write-Host "  stopped PID $procId"
    }
}
Start-Sleep -Seconds 2

Write-Host "=== [2/4] Start API (new code) ===" -ForegroundColor Cyan
$backend = Join-Path $Root "backend"
Start-Process -WindowStyle Hidden -FilePath "py" `
    -ArgumentList "-3.12", "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory $backend | Out-Null

$ready = $false
for ($i = 0; $i -lt 45; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
    Start-Sleep -Seconds 1
}
if (-not $ready) {
    Write-Host "API failed to start on :8000" -ForegroundColor Red
    exit 1
}
Write-Host "  API ready on :8000"

Write-Host "=== [3/4] Ingest kicona (from cache if available) ===" -ForegroundColor Cyan
Set-Location $Root
$cache = Join-Path $Root "collector\samples\e2e\kicona_amagasaki_full.json"
if (Test-Path $cache) {
    py -3.12 scripts/e2e_local.py --store kicona_amagasaki --from-cache
} else {
    py -3.12 scripts/e2e_local.py --store kicona_amagasaki
}

Write-Host "=== [4/4] verify_all ===" -ForegroundColor Cyan
py -3.12 scripts/verify_all.py
$code = $LASTEXITCODE

Write-Host ""
Write-Host "API is running in background on :8000 (stop the uvicorn process to end)." -ForegroundColor Yellow
Write-Host "Done. Exit code: $code"
exit $code
