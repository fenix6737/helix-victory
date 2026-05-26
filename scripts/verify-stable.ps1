# 安定性スモークテスト — API/UI/トンネル/公開URL
param(
    [string]$Root = (Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent)
)

$ErrorActionPreference = "Continue"
. (Join-Path $Root "scripts\helix-core.ps1")

$health = Test-HelixStackHealthy -Root $Root -CheckTunnel
$prod = Test-HelixFrontendProductionReady -Root $Root
$jsonPath = Join-Path $Root "data\public-url.json"

Write-Host ""
Write-Host "Helix stability check" -ForegroundColor Cyan
Write-Host "  API health:    $($health.Api)"
Write-Host "  UI health:     $($health.Ui)"
Write-Host "  Tunnel health: $($health.Tunnel)"
Write-Host "  Production UI: $prod"
Write-Host "  public-url.json: $(Test-Path $jsonPath)"
if (Test-Path $jsonPath) {
    $m = Get-Content $jsonPath -Raw | ConvertFrom-Json
    Write-Host "  URL: $($m.welcome_url)"
}
Write-Host "  Overall OK:    $($health.Ok)"
Write-Host ""

if (-not $health.Ok) { exit 1 }
exit 0
