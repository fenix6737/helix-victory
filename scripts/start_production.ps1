# Helix Victory production startup - API + collectors + frontend
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
Set-Location $Root

if (Get-Command docker -ErrorAction SilentlyContinue) {
    Write-Host "Starting redis and postgres via docker compose..." -ForegroundColor Cyan
    docker compose up -d redis postgres
    Start-Sleep -Seconds 5
} else {
    Write-Host "Docker not found - cache will use degraded memory fallback" -ForegroundColor Yellow
}

$procId = (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess
if ($procId) { Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue; Start-Sleep -Seconds 2 }

Write-Host "Starting API on port 8000..." -ForegroundColor Cyan
Start-Process -WindowStyle Hidden -FilePath "py" `
    -ArgumentList "-3.12","-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000" `
    -WorkingDirectory (Join-Path $Root "backend")

for ($i = 0; $i -lt 30; $i++) {
    try {
        if ((Invoke-WebRequest "http://127.0.0.1:8000/health" -TimeoutSec 2).StatusCode -eq 200) { break }
    } catch {}
    Start-Sleep -Seconds 1
}

Write-Host "Starting collector daemon (kicona + maruhan)..." -ForegroundColor Cyan
Start-Process -WindowStyle Hidden -FilePath "py" `
    -ArgumentList "-3.12","-m","collector.daemon","--stores","kicona_amagasaki,maruhan_umeda" `
    -WorkingDirectory (Join-Path $Root "collector")

Write-Host "Starting frontend on port 3000..." -ForegroundColor Cyan
Start-Process -FilePath "npm" -ArgumentList "run","dev" -WorkingDirectory (Join-Path $Root "frontend")

Write-Host ""
Write-Host "Ready:" -ForegroundColor Green
Write-Host "  API  http://127.0.0.1:8000"
Write-Host "  UI   http://127.0.0.1:3000"
Write-Host "  Maruhan live collect: py -3.12 scripts/collect_maruhan_live.py"
Write-Host "  Tests: py -3.12 scripts/run_all_tests.py"
