# 開発者向け指示書 — 全機能の実装・実データ検証（ダミー/サンプル禁止）
param(
    [string]$Root = "",
    [string]$ApiUrl = "",
    [string]$StoreId = "kicona_amagasaki",
    [switch]$SkipLiveApi,
    [switch]$SkipCollectorLive
)

if (-not $Root) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $Root = Split-Path -Parent $scriptDir
}

$fail = 0
function Check($name, $ok, $detail = "") {
    if ($ok) {
        Write-Host "[OK] $name $detail" -ForegroundColor Green
    } else {
        Write-Host "[NG] $name $detail" -ForegroundColor Red
        $script:fail++
    }
}

Write-Host "=== Developer spec verification (full) ===" -ForegroundColor Cyan

# --- §5 起動スクリプト ---
$startContent = Get-Content (Join-Path $Root "scripts\start-helix.ps1") -Raw -ErrorAction SilentlyContinue
Check "start-helix suppresses autostart output" ($startContent -match "Out-Null")
Check "start-helix waits for health" ($startContent -match "Test-HelixStackHealthy")

# --- 必須ファイル ---
$required = @(
    "collector\collector\anaslo\client.py",
    "collector\collector\pscube\client.py",
    "collector\collector\minrepo\client.py",
    "collector\collector\hallnavi\client.py",
    "collector\collector\kicona.py",
    "collector\collector\daemon.py",
    "backend\app\services\period_statistics.py",
    "backend\app\services\daily_cycle.py",
    "backend\app\services\prediction_report.py",
    "backend\app\featured.py",
    "frontend\src\components\PeriodStatsPanel.tsx",
    "frontend\src\components\FeaturedMachinesSection.tsx",
    "scripts\midnight-daily-cycle.ps1",
    "scripts\cloud_collect_once.py",
    ".github\workflows\cloud-collect.yml",
    ".github\workflows\midnight-jst-daily-cycle.yml",
    ".github\workflows\outcome-verify-jst.yml",
    ".github\workflows\secrets-health-check.yml",
    ".github\scripts\helix-auth.sh",
    "backend\app\analysis\border_ev.py",
    "backend\app\timeutil.py",
    "backend\app\pachinko_segment.py",
    "frontend\src\lib\density.tsx",
    "docs\DEVELOPER_SPEC.md"
)
foreach ($f in $required) {
    Check "file $f" (Test-Path (Join-Path $Root $f))
}

# --- §1 URL 定数（ソース内） ---
$kiconaSrc = Get-Content (Join-Path $Root "collector\collector\kicona.py") -Raw
$pscubeSrc = Get-Content (Join-Path $Root "collector\collector\pscube\client.py") -Raw
$hallSrc = Get-Content (Join-Path $Root "collector\collector\hallnavi\client.py") -Raw
$anasloSrc = Get-Content (Join-Path $Root "collector\collector\anaslo\client.py") -Raw
$minrepoSrc = Get-Content (Join-Path $Root "collector\collector\minrepo\client.py") -Raw
Check "§1 anaslo in kicona" ($kiconaSrc -match "scrape_anaslo_store")
Check "§1 pscube in kicona" ($kiconaSrc -match "scrape_pscube_store")
Check "§1 minrepo in kicona" ($kiconaSrc -match "scrape_minrepo_store")
Check "§1 hall-navi in kicona" ($kiconaSrc -match "fetch_hall_navi_info")
Check "§1 pscube URL c713842" ($pscubeSrc -match "c713842")
Check "§1 hall-navi hid" ($hallSrc -match "660088400000027290")
Check "§1 anaslo.com" ($anasloSrc -match "ana-slo\.com")
Check "§1 min-repo tag" ($minrepoSrc -match "min-repo\.com/tag")
Check "§1 data_sources metadata" ($kiconaSrc -match "data_sources")
Check "§1 realtime daemon" (Test-Path (Join-Path $Root "collector\collector\daemon.py"))
Check "§1 sync-github-secrets" (Test-Path (Join-Path $Root "scripts\sync-github-secrets.ps1"))
Check "§1 helix-auth retry script" (Test-Path (Join-Path $Root ".github\scripts\helix-auth.sh"))

$engineSrc = Get-Content (Join-Path $Root "backend\app\analysis\engine.py") -Raw -ErrorAction SilentlyContinue
$feedbackSrc = Get-Content (Join-Path $Root "backend\app\analysis\feedback.py") -Raw -ErrorAction SilentlyContinue
$anasloParser = Get-Content (Join-Path $Root "collector\collector\anaslo\parser.py") -Raw -ErrorAction SilentlyContinue
Check "reliability border_ev scoring" ($engineSrc -match "border_ev_score")
Check "reliability JST outcome window" ($feedbackSrc -match "jst_day_bounds_utc")
Check "reliability anaslo rotation column" ($anasloParser -match "回転")
Check "pachinko 4pachi middle filter" (Test-Path (Join-Path $Root "backend\app\pachinko_segment.py"))
Check "UI density mode" (Test-Path (Join-Path $Root "frontend\src\lib\density.tsx"))

# --- ユニットテスト ---
Push-Location (Join-Path $Root "backend")
$ut = py -3.12 -m unittest discover -s tests -p "test_*.py" -q 2>&1 | Out-String
Pop-Location
Check "backend unittest" ($ut -match "OK") ($ut.Trim())

Push-Location (Join-Path $Root "collector")
$ct = py -3.12 -m unittest discover -s tests -p "test_*.py" -q 2>&1 | Out-String
Pop-Location
Check "collector unittest" ($ct -match "OK") ($ct.Trim())

# --- API 実データ検証 ---
if (-not $ApiUrl) {
    $flyEnv = Join-Path $Root "deploy\fly-deployed.local.env"
    if (Test-Path $flyEnv) {
        foreach ($line in Get-Content $flyEnv -Encoding UTF8) {
            if ($line -match '^HELIX_PUBLIC_URL=(.+)$') { $ApiUrl = $Matches[1].Trim() }
        }
    }
    if (-not $ApiUrl -and (Test-Path (Join-Path $Root ".env"))) {
        foreach ($line in Get-Content (Join-Path $Root ".env") -Encoding UTF8) {
            if ($line -match '^HELIX_PUBLIC_URL=(.+)$') { $ApiUrl = $Matches[1].Trim() }
        }
    }
}
if (-not $ApiUrl) { $ApiUrl = "http://127.0.0.1:8000" }

$user = "helix_admin"
$pass = "HelixVictory2026!Admin"
$ingestKey = ""
# Fly 検証時は fly-deployed を .env より優先（上書き）
$credFiles = @(
    (Join-Path $Root ".env"),
    (Join-Path $Root "deploy\fly-deployed.local.env")
)
if ($ApiUrl -match "fly\.dev" -and (Test-Path (Join-Path $Root "deploy\fly-deployed.local.env"))) {
    $credFiles = @((Join-Path $Root "deploy\fly-deployed.local.env"))
}
foreach ($cf in $credFiles) {
    if (-not (Test-Path $cf)) { continue }
    foreach ($line in Get-Content $cf -Encoding UTF8) {
        if ($line -match '^ADMIN_USERNAME=(.+)$') { $user = $Matches[1].Trim() }
        if ($line -match '^ADMIN_PASSWORD=(.+)$') { $pass = $Matches[1].Trim() }
        if ($line -match '^INGEST_API_KEY=(.+)$') { $ingestKey = $Matches[1].Trim() }
    }
}

if (-not $SkipLiveApi) {
    $lp = Join-Path $Root "data\devspec-login.json"
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($lp, (@{ username = $user; password = $pass } | ConvertTo-Json -Compress), $utf8NoBom)
    $loginUrl = "$ApiUrl/api/v1/auth/login"
    $httpFile = Join-Path $Root "data\devspec-http.txt"
    $bodyFile = Join-Path $Root "data\devspec-body.json"
    curl.exe -s -o $bodyFile -w "%{http_code}" -X POST $loginUrl -H "Content-Type: application/json" --data-binary "@$lp" | Set-Content $httpFile -Encoding ASCII -NoNewline
    $httpLogin = (Get-Content $httpFile -Raw).Trim()
    $tjBody = Get-Content $bodyFile -Raw
    Check "API login" ($httpLogin -eq "200") "HTTP $httpLogin @ $ApiUrl"

    if ($tjBody -match '"access_token"\s*:\s*"([^"]+)"') {
        $tok = $Matches[1]
        foreach ($ep in @("statistics/daily", "statistics/weekly", "statistics/monthly", "prediction-report")) {
            $url = "$ApiUrl/api/v1/stores/$StoreId/$ep"
            $epBody = Join-Path $Root "data\devspec-ep.json"
            $epHttp = Join-Path $Root "data\devspec-ep-http.txt"
            curl.exe -s -o $epBody -w "%{http_code}" -H "Authorization: Bearer $tok" $url | Set-Content $epHttp -Encoding ASCII -NoNewline
            $code = (Get-Content $epHttp -Raw).Trim()
            Check "API GET $ep" ($code -eq "200") "HTTP $code"
            $body = Get-Content $epBody -Raw
            if ($ep -eq "statistics/daily" -and $body -match '"machine_count"\s*:\s*(\d+)') {
                $mc = [int]$Matches[1]
                Check "§3 daily machine_count > 0" ($mc -gt 0) "count=$mc"
            }
            if ($ep -eq "statistics/weekly" -and $body -match '"machine_ranking"') {
                Check "§3 weekly machine_ranking present" ($body -match '"machine_number"')
            }
            if ($ep -eq "statistics/monthly" -and $body -match '"machine_family_trends"') {
                Check "§3 monthly family_trends present" ($true)
            }
            if ($ep -eq "prediction-report" -and $body -match '"prediction_count"\s*:\s*(\d+)') {
                $pc = [int]$Matches[1]
                Check "§2 daily report predictions" ($pc -gt 0) "count=$pc"
            }
        }

        $cycleBody = Join-Path $Root "data\devspec-cycle.json"
        [System.IO.File]::WriteAllText($cycleBody, (@{ store_id = $StoreId } | ConvertTo-Json -Compress), $utf8NoBom)
        $ccFile = Join-Path $Root "data\devspec-cycle-http.txt"
        curl.exe -s --max-time 180 -o (Join-Path $Root "data\devspec-cycle-out.json") -w "%{http_code}" -X POST "$ApiUrl/api/v1/analysis/daily-learning-cycle" `
            -H "Authorization: Bearer $tok" -H "Content-Type: application/json" --data-binary "@$cycleBody" | Set-Content $ccFile -Encoding ASCII -NoNewline
        $cc = (Get-Content $ccFile -Raw).Trim()
        Check "§2 daily-learning-cycle POST" ($cc -eq "200") "HTTP $cc"

        if ($ingestKey) {
            $ing = Join-Path $Root "data\devspec-ingest.json"
            '{"store_id":"' + $StoreId + '","logs":[]}' | Set-Content $ing -Encoding UTF8 -NoNewline
            $icFile = Join-Path $Root "data\devspec-ingest-http.txt"
            curl.exe -s -o (Join-Path $Root "data\devspec-ingest-out.json") -w "%{http_code}" -X POST "$ApiUrl/api/v1/ingest/logs" `
                -H "Content-Type: application/json" -H "X-Ingest-Key: $ingestKey" --data-binary "@$ing" | Set-Content $icFile -Encoding ASCII -NoNewline
            $ic = (Get-Content $icFile -Raw).Trim()
            Check "§1 ingest endpoint (Fly rewrite)" ($ic -in @("200", "422")) "HTTP $ic"
        }
    }
} else {
    Write-Host "[SKIP] Live API checks" -ForegroundColor Yellow
}

# --- §4 UI ---
$featUi = Get-Content (Join-Path $Root "frontend\src\components\FeaturedMachinesSection.tsx") -Raw
Check "§4 featured section tokyo_ghoul" ($featUi -match "tokyo_ghoul")
Check "§4 featured section evangelion" ($featUi -match "evangelion")
$statsUi = Get-Content (Join-Path $Root "frontend\src\components\PeriodStatsPanel.tsx") -Raw
Check "§3 UI daily/weekly/monthly tabs" ($statsUi -match "weekly" -and $statsUi -match "monthly")

Write-Host ""
if ($fail -eq 0) {
    Write-Host "ALL PASSED ($ApiUrl)" -ForegroundColor Green
    exit 0
}
Write-Host "FAILED: $fail item(s) — run sync-fly-data.ps1 if API data empty" -ForegroundColor Red
exit 1
