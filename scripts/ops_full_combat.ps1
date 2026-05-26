# Helix Victory — 100%運用ブートストラップ
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
Set-Location $Root

Write-Host "=== [1] Docker Redis + Postgres ===" -ForegroundColor Cyan
docker compose up -d redis postgres 2>&1 | Out-Null
Start-Sleep -Seconds 5

Write-Host "=== [2] API restart ===" -ForegroundColor Cyan
& (Join-Path $Root "scripts\ops_priority1.ps1") -ErrorAction SilentlyContinue
$pids = @(Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
foreach ($procId in $pids) { if ($procId) { Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue } }
Start-Sleep -Seconds 2
$backend = Join-Path $Root "backend"
Start-Process -WindowStyle Hidden -FilePath "py" -ArgumentList "-3.12","-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000" -WorkingDirectory $backend | Out-Null
for ($i = 0; $i -lt 45; $i++) {
    try { if ((Invoke-WebRequest "http://127.0.0.1:8000/health" -TimeoutSec 2).StatusCode -eq 200) { break } } catch {}
    Start-Sleep -Seconds 1
}

Write-Host "=== [3] Kicona ingest ===" -ForegroundColor Cyan
py -3.12 scripts/e2e_local.py --store kicona_amagasaki --from-cache

Write-Host "=== [4] Maruhan seed + ingest ===" -ForegroundColor Cyan
py -3.12 scripts/seed_maruhan_sample.py
if ($LASTEXITCODE -ne 0) { Write-Host "Maruhan seed failed (check sample HTML)" -ForegroundColor Yellow }

Write-Host "=== [5] Full test battery ===" -ForegroundColor Cyan
py -3.12 scripts/run_all_tests.py
exit $LASTEXITCODE
