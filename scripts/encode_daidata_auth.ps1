# daidata_auth.json → GitHub Secret DAIDATA_AUTH_B64 用
param(
    [string]$Path = "collector\daidata_auth.json"
)
$full = Join-Path (Split-Path $PSScriptRoot -Parent) $Path
if (-not (Test-Path $full)) {
    Write-Error "Not found: $full — run daidata_login.py first"
    exit 1
}
$b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($full))
Write-Host "Copy to GitHub Secret: DAIDATA_AUTH_B64"
Write-Host $b64
