# 深夜0時以降の日次学習サイクル（全店舗）
param(
    [string]$Root = (Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent),
    [string[]]$Stores = @("kicona_amagasaki", "maruhan_umeda")
)

$ErrorActionPreference = "Continue"
$log = Join-Path $Root "data\midnight-cycle.log"
function Log($m) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $m
    Add-Content -Path $log -Value $line -Encoding UTF8
    Write-Host $line
}

. (Join-Path $Root "scripts\helix-core.ps1")
$api = "http://127.0.0.1:8000"
foreach ($envFile in @(
    (Join-Path $Root "deploy\fly-deployed.local.env"),
    (Join-Path $Root ".env")
)) {
    if (-not (Test-Path $envFile)) { continue }
    foreach ($line in Get-Content $envFile -Encoding UTF8) {
        if ($line -match '^ADMIN_PASSWORD=(.+)$') { $pass = $Matches[1].Trim() }
        if ($line -match '^ADMIN_USERNAME=(.+)$') { $user = $Matches[1].Trim() }
        if ($line -match '^HELIX_PUBLIC_URL=(.+)$') { $api = $Matches[1].Trim() }
    }
}
$user = if ($user) { $user } else { "helix_admin" }
$pass = if ($pass) { $pass } else { "HelixVictory2026!Admin" }

$loginPath = Join-Path $Root "data\login-test.json"
@{ username = $user; password = $pass } | ConvertTo-Json -Compress | Set-Content $loginPath -Encoding UTF8
$loginUrl = "$api/api/v1/auth/login"
$tokenJson = curl.exe -s -X POST $loginUrl -H "Content-Type: application/json" --data-binary "@$loginPath"
if ($tokenJson -notmatch '"access_token"\s*:\s*"([^"]+)"') {
    Log "FAIL login"
    exit 1
}
$token = $Matches[1]
Log "===== midnight daily learning cycle ====="

foreach ($sid in $Stores) {
    $bodyPath = Join-Path $Root "data\midnight-body.json"
    @{ store_id = $sid } | ConvertTo-Json -Compress | Set-Content $bodyPath -Encoding UTF8
    $res = curl.exe -s -X POST "$api/api/v1/analysis/daily-learning-cycle" `
        -H "Authorization: Bearer $token" -H "Content-Type: application/json" --data-binary "@$bodyPath"
    Log "$sid -> $res"
}
Log "done"
exit 0
