# リアルタイム性・推奨件数・角台33の検証
param(
    [string]$ApiUrl = "https://helix-victory.fly.dev",
    [string]$StoreId = "kicona_amagasaki"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$fail = 0
function Check($name, $ok, $detail = "") {
    if ($ok) { Write-Host "[OK] $name $detail" -ForegroundColor Green }
    else { Write-Host "[NG] $name $detail" -ForegroundColor Red; $script:fail++ }
}

$envFile = Join-Path $Root "deploy\fly-deployed.local.env"
$user = "helix_admin"
$pw = ""
$ingestKey = ""
if (Test-Path $envFile) {
    foreach ($line in Get-Content $envFile -Encoding UTF8) {
        if ($line -match '^ADMIN_USERNAME=(.+)$') { $user = $Matches[1].Trim() }
        if ($line -match '^ADMIN_PASSWORD=(.+)$') { $pw = $Matches[1].Trim() }
        if ($line -match '^INGEST_API_KEY=(.+)$') { $ingestKey = $Matches[1].Trim() }
    }
}
if (-not $pw) { Write-Host "ADMIN_PASSWORD not found in deploy/fly-deployed.local.env"; exit 1 }

$lp = Join-Path $Root "data\verify-login.json"
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($lp, (@{ username = $user; password = $pw } | ConvertTo-Json -Compress), $utf8NoBom)
$bodyFile = Join-Path $Root "data\verify-body.json"
$httpFile = Join-Path $Root "data\verify-http.txt"
curl.exe -s -o $bodyFile -w "%{http_code}" -X POST "$ApiUrl/api/v1/auth/login" -H "Content-Type: application/json" --data-binary "@$lp" | Set-Content $httpFile -Encoding ASCII -NoNewline
$httpLogin = (Get-Content $httpFile -Raw).Trim()
$tjBody = Get-Content $bodyFile -Raw
Check "login HTTP 200" ($httpLogin -eq "200") "HTTP $httpLogin"
$tok = ""
if ($tjBody -match '"access_token"\s*:\s*"([^"]+)"') { $tok = $Matches[1] }
Check "login token" ($tok.Length -gt 10)
if (-not $tok) { exit 1 }

function Get-Json($url) {
    $out = Join-Path $Root "data\verify-tmp.json"
    curl.exe -s -o $out -H "Authorization: Bearer $tok" $url
    Get-Content $out -Raw -Encoding UTF8 | ConvertFrom-Json
}

$live = Get-Json "$ApiUrl/api/v1/stores/$StoreId/live-status"
Check "live-status" ($live.store_id -eq $StoreId) "sync_age=$($live.sync_age_minutes) ingest_age=$($live.ingest_age_minutes) analysis_age=$($live.analysis_age_minutes)"
if ($null -ne $live.sync_age_minutes) {
    Check "sync within 30min" ($live.sync_age_minutes -le 30) "sync_age=$($live.sync_age_minutes)"
} elseif ($null -ne $live.ingest_age_minutes) {
    Check "ingest within 30min (fallback)" ($live.ingest_age_minutes -le 30) "age=$($live.ingest_age_minutes)"
} else {
    Write-Host "[WARN] no sync/ingest timestamps" -ForegroundColor Yellow
    $script:fail++
}
if ($null -ne $live.analysis_age_minutes) {
    Check "analysis within 30min" ($live.analysis_age_minutes -le 30) "age=$($live.analysis_age_minutes)"
} else {
    Write-Host "[WARN] analysis_age_minutes null" -ForegroundColor Yellow
    $script:fail++
}
Check "realtime_mode label" ($live.realtime_mode -match "収集") "mode=$($live.realtime_mode)"

foreach ($gt in @("slot", "pachinko")) {
    $rec = Get-Json "$ApiUrl/api/v1/recommendations/today?store_id=$StoreId&game_type=$gt"
    $n = @($rec.recommend).Count
    Check "recommend count $gt" ($n -ge 3) "count=$n hold=$(@($rec.hold).Count) exclude=$(@($rec.exclude_preview).Count)"
}

$machines = Get-Json "$ApiUrl/api/v1/recommendations/today?store_id=$StoreId&game_type=slot"
$all = @($machines.recommend) + @($machines.hold) + @($machines.exclude_preview)
$ghoul = $all | Where-Object { $_.title -like "*喰種*" -or $_.title -like "*GHOUL*" }
Check "tokyo ghoul in data" ($ghoul.Count -gt 0) "machines=$($ghoul.Count)"
$withAtari = $ghoul | Where-Object { $null -ne $_.daily_atari_total }
Check "ghoul daily_atari_total field" ($withAtari.Count -gt 0) "with_data=$($withAtari.Count)/$($ghoul.Count)"
$high = $ghoul | Where-Object { $_.daily_atari_total -ge 10 }
if ($high.Count -gt 0) {
    $top = $high | Sort-Object { $_.daily_atari_total } -Descending | Select-Object -First 1
    Write-Host "[INFO] ghoul top atari: $($top.machine_number)番 total=$($top.daily_atari_total)" -ForegroundColor Cyan
} else {
    Write-Host "[WARN] ghoul BB/RB not in feed yet — floor 33-hit day may not appear until anaslo has counts" -ForegroundColor Yellow
}

if ($ingestKey) {
    $ingPath = Join-Path $Root "data\verify-ingest.json"
    $ingJson = @{
        store_id = $StoreId
        logs     = @(
            @{
                machine_number = 481
                title          = "L東京喰種"
                captured_at    = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
                diff_coins     = 100
                big_count      = 20
                reg_count      = 13
                rotation_count = 5000
                final_games    = 400
                game_type      = "slot"
                source         = "verify"
            }
        )
    } | ConvertTo-Json -Depth 5 -Compress
    [System.IO.File]::WriteAllText($ingPath, $ingJson, $utf8NoBom)
    $ingBody = Join-Path $Root "data\verify-ingest-resp.json"
    curl.exe -s -o $ingBody -X POST "$ApiUrl/api/v1/ingest/logs" -H "Content-Type: application/json" -H "X-Ingest-Key: $ingestKey" --data-binary "@$ingPath"
    $ingRes = Get-Content $ingBody -Raw | ConvertFrom-Json
    Check "ingest analysis_ran" ($ingRes.analysis_ran -eq $true) "inserted=$($ingRes.inserted) recs=$($ingRes.recommendations_created)"
    Start-Sleep -Seconds 2
    $after = Get-Json "$ApiUrl/api/v1/recommendations/today?store_id=$StoreId&game_type=slot"
    $areaAfter = @($after.recommend) + @($after.hold) + @($after.exclude_preview) | Where-Object {
        $_.title -like "*喰種*" -and $_.machine_number -ge 474 -and $_.machine_number -le 483
    }
    Check "L ghoul after ingest listed" ($areaAfter.Count -gt 0) "atari=$($areaAfter[0].daily_atari_total)"
}

if ($fail -gt 0) { exit 1 }
Write-Host "`nALL REALTIME CHECKS PASSED" -ForegroundColor Cyan
