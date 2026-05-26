# Fly へスクレイプ → ingest → 分析（PCで1回実行、数分かかります）
# 前提: deploy-fly-deployed.local.env が存在すること
$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $MyInvocation.MyCommand.Path) -Parent
Set-Location $Root

$envFile = Join-Path $Root "deploy\fly-deployed.local.env"
if (-not (Test-Path $envFile)) {
    Write-Host "Missing $envFile — run deploy-fly-simple.ps1 first" -ForegroundColor Red
    exit 1
}

Get-Content $envFile -Encoding UTF8 | ForEach-Object {
    if ($_ -match '^([^#=]+)=(.*)$') {
        Set-Item -Path "env:$($matches[1])" -Value $matches[2].Trim()
    }
}

$env:HELIX_API_URL = $env:HELIX_PUBLIC_URL
if (-not $env:HELIX_API_URL) { $env:HELIX_API_URL = "https://helix-victory.fly.dev" }
$env:API_URL = $env:HELIX_API_URL

Write-Host "Sync to Fly: $env:HELIX_API_URL" -ForegroundColor Cyan
$py = Get-Command py -ErrorAction SilentlyContinue
$prev = $ErrorActionPreference
$ErrorActionPreference = "Continue"
if ($py) {
    & py -3.12 -m playwright install chromium 2>$null | Out-Null
    & py -3.12 $Root\scripts\cloud_collect_once.py
} else {
    python -m playwright install chromium 2>$null | Out-Null
    python $Root\scripts\cloud_collect_once.py
}
$ErrorActionPreference = $prev

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Done. Open: $env:HELIX_API_URL/welcome (login for dashboard)" -ForegroundColor Green
