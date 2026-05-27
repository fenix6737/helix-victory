# リアルタイム性・推奨件数・角台33の検証
param(
    [string]$ApiUrl = "https://helix-victory.fly.dev",
    [string]$StoreId = "kicona_amagasaki"
)

$ErrorActionPreference = "Stop"
$fail = 0
function Check($name, $ok, $detail = "") {
    if ($ok) { Write-Host "[OK] $name $detail" -ForegroundColor Green }
    else { Write-Host "[NG] $name $detail" -ForegroundColor Red; $script:fail++ }
}

$envFile = Join-Path (Split-Path $PSScriptRoot -Parent) "deploy\fly-deployed.local.env"
if (-not (Test-Path $envFile)) { $envFile = Join-Path $PSScriptRoot "..\deploy\fly-deployed.local.env" }
$pw = ""
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^ADMIN_PASSWORD=(.+)$') { $pw = $Matches[1].Trim() }
    }
}
if (-not $pw) { Write-Host "ADMIN_PASSWORD not found in deploy/fly-deployed.local.env"; exit 1 }

$loginBody = @{ username = "helix_admin"; password = $pw } | ConvertTo-Json -Compress
$login = curl.exe -s -X POST "$ApiUrl/api/v1/auth/login" -H "Content-Type: application/json" -d $loginBody | ConvertFrom-Json
$tok = $login.access_token
Check "login" ($tok.Length -gt 10)

$live = curl.exe -s "$ApiUrl/api/v1/stores/$StoreId/live-status" -H "Authorization: Bearer $tok" | ConvertFrom-Json
Check "live-status" ($live.store_id -eq $StoreId) "ingest_age=$($live.ingest_age_minutes) analysis_age=$($live.analysis_age_minutes)"
Check "ingest within 30min" ($live.ingest_age_minutes -ne $null -and $live.ingest_age_minutes -le 30) "age=$($live.ingest_age_minutes)"
Check "analysis within 30min" ($live.analysis_age_minutes -ne $null -and $live.analysis_age_minutes -le 30) "age=$($live.analysis_age_minutes)"

foreach ($gt in @("slot", "pachinko")) {
    $rec = curl.exe -s "$ApiUrl/api/v1/recommendations/today?store_id=$StoreId&game_type=$gt" -H "Authorization: Bearer $tok" | ConvertFrom-Json
    $n = $rec.recommend.Count
    Check "recommend count $gt" ($n -ge 3) "count=$n hold=$($rec.hold.Count)"
}

# 東京喰種 33番台
$machines = curl.exe -s "$ApiUrl/api/v1/recommendations/today?store_id=$StoreId&game_type=slot" -H "Authorization: Bearer $tok" | ConvertFrom-Json
$all = @($machines.recommend) + @($machines.hold) + @($machines.exclude_preview)
$ghoul = $all | Where-Object { $_.title -match "喰種" -or $_.title -match "GHOUL" }
$m33 = $all | Where-Object { $_.machine_number -eq 33 }
Check "tokyo ghoul in data" ($ghoul.Count -gt 0) "machines=$($ghoul.Count)"
if ($m33) {
    Check "machine 33 position corner" ($m33.position_type -eq "corner") "pos=$($m33.position_type)"
} else {
    Write-Host "[WARN] machine 33 not in today's lists — check raw_logs ingest" -ForegroundColor Yellow
}

# ingest triggers analysis
$ing = '{"store_id":"' + $StoreId + '","logs":[{"machine_number":33,"title":"L東京喰種","captured_at":"2026-05-27T12:00:00Z","diff_coins":100,"rotation_count":5000,"final_games":400,"game_type":"slot","source":"verify"}]}'
$ingRes = curl.exe -s -X POST "$ApiUrl/api/v1/ingest/logs" -H "Content-Type: application/json" -H "X-Ingest-Key: $((Get-Content $envFile | Where-Object { $_ -match '^INGEST_API_KEY=' }) -replace 'INGEST_API_KEY=','')" -d $ing | ConvertFrom-Json
Check "ingest analysis_ran" ($ingRes.analysis_ran -eq $true) "inserted=$($ingRes.inserted) recs=$($ingRes.recommendations_created)"

if ($fail -gt 0) { exit 1 }
Write-Host "`nALL REALTIME CHECKS PASSED" -ForegroundColor Cyan
