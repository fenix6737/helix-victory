# 最終システムテスト — 接続・API・リアルタイム・文言
param(
    [string]$Root = (Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent),
    [switch]$SkipTunnel
)

$ErrorActionPreference = "Continue"
. (Join-Path $Root "scripts\helix-core.ps1")

$report = @()
function Add-Result($name, $ok, $detail = "") {
    $script:report += [pscustomobject]@{ Test = $name; OK = $ok; Detail = $detail }
}

# 1. 接続・安定
$health = Test-HelixStackHealthy -Root $Root -CheckTunnel:(-not $SkipTunnel)
Add-Result "Stack health" $health.Ok ("api=$($health.Api) ui=$($health.Ui) tunnel=$($health.Tunnel)")

$timings = @()
foreach ($pair in @(
        @("local_welcome", "http://127.0.0.1:3000/welcome"),
        @("api_health", "http://127.0.0.1:8000/health"),
        @("api_combat", "http://127.0.0.1:8000/health/combat")
    )) {
    $t = (Measure-Command {
        $code = curl.exe -s -o NUL -w "%{http_code}" --max-time 10 $pair[1] 2>$null
    }).TotalMilliseconds
    $ok = $code -eq "200"
    Add-Result $pair[0] $ok ("${t}ms HTTP $code")
}

# 2. API（認証）
$adminUser = "helix_admin"
$adminPass = $null
if (Test-Path (Join-Path $Root ".env")) {
    foreach ($line in Get-Content (Join-Path $Root ".env") -Encoding UTF8) {
        if ($line -match '^ADMIN_PASSWORD=(.+)$') { $adminPass = $Matches[1].Trim() }
        if ($line -match '^ADMIN_USERNAME=(.+)$') { $adminUser = $Matches[1].Trim() }
    }
}
if (-not $adminPass) {
    $envFile = Join-Path $Root "deploy\fly-deployed.local.env"
    if (Test-Path $envFile) {
        foreach ($line in Get-Content $envFile -Encoding UTF8) {
            if ($line -match '^ADMIN_PASSWORD=(.+)$') { $adminPass = $Matches[1].Trim() }
        }
    }
}

if ($adminPass) {
    $loginPath = Join-Path $Root "data\login-test.json"
    [System.IO.File]::WriteAllText(
        $loginPath,
        (@{ username = $adminUser; password = $adminPass } | ConvertTo-Json -Compress)
    )
    $tokenJson = curl.exe -s -X POST "http://127.0.0.1:8000/api/v1/auth/login" `
        -H "Content-Type: application/json" --data-binary "@$loginPath" 2>$null
    $token = $null
    if ($tokenJson -match '"access_token"\s*:\s*"([^"]+)"') { $token = $Matches[1] }
    Add-Result "Admin login" ([bool]$token) $(if ($token) { "OK" } else { "failed" })

    if ($token) {
        foreach ($ep in @(
                @("rec_kicona", "http://127.0.0.1:8000/api/v1/recommendations/today?store_id=kicona_amagasaki&game_type=slot"),
                @("rec_maruhan", "http://127.0.0.1:8000/api/v1/recommendations/today?store_id=maruhan_umeda&game_type=slot"),
                @("live_ev", "http://127.0.0.1:8000/api/v1/stores/kicona_amagasaki/live-ev?game_type=slot"),
                @("live_status", "http://127.0.0.1:8000/api/v1/stores/kicona_amagasaki/live-status"),
                @("extras", "http://127.0.0.1:8000/api/v1/stores/kicona_amagasaki/extras")
            )) {
            $ms = (Measure-Command {
                $body = curl.exe -s -w "`n%{http_code}" -H "Authorization: Bearer $token" --max-time 15 $ep[1] 2>$null
            }).TotalMilliseconds
            $lines = $body -split "`n"
            $code = $lines[-1]
            $ok = $code -eq "200"
            $count = ""
            if ($ok -and $ep[0] -like "rec_*") {
                if ($body -match '"recommend"\s*:\s*\[') { $count = "has recommend" }
            }
            Add-Result $ep[0] $ok "${ms}ms $code $count"
        }

        # 詳細ページ用 machine id
        $rec = curl.exe -s -H "Authorization: Bearer $token" `
            "http://127.0.0.1:8000/api/v1/recommendations/today?store_id=kicona_amagasaki&game_type=slot"
        if ($rec -match '"machine_id"\s*:\s*(\d+)') {
            $mid = $Matches[1]
            $ms = (Measure-Command {
                $code = curl.exe -s -o NUL -w "%{http_code}" -H "Authorization: Bearer $token" `
                    --max-time 10 "http://127.0.0.1:8000/api/v1/machines/$mid" 2>$null
            }).TotalMilliseconds
            Add-Result "machine_detail" ($code -eq "200") "${ms}ms id=$mid HTTP $code"
        } else {
            Add-Result "machine_detail" $false "no machine_id in recommendations"
        }
    }
} else {
    Add-Result "Admin login" $false "ADMIN_PASSWORD not found"
}

# 3. 収集デーモン
$collector = Get-HelixCollectorProcesses | Select-Object -First 1
Add-Result "Collector daemon" ([bool]$collector) $(if ($collector) { "pid $($collector.ProcessId)" } else { "not running" })

# 4. 単体テスト
Push-Location (Join-Path $Root "backend")
try {
    $ut = & py -3.12 -m unittest discover -s tests -p "test_*.py" -q 2>&1 | Out-String
} finally {
    Pop-Location
}
Add-Result "Backend unittest" ($ut -match "Ran \d+ tests" -and $ut -match "OK") $ut.Trim().Split("`n")[-1]

# Report
Write-Host ""
Write-Host "=== Helix Victory Final Test ===" -ForegroundColor Cyan
$fail = 0
foreach ($r in $report) {
    $color = if ($r.OK) { "Green" } else { "Red"; $script:fail++ }
    Write-Host ("[{0}] {1} — {2}" -f $(if ($r.OK) { "OK" } else { "NG" }), $r.Test, $r.Detail) -ForegroundColor $color
}
Write-Host ""
if ($fail -eq 0) {
    Write-Host "ALL PASSED ($($report.Count) checks)" -ForegroundColor Green
    exit 0
}
Write-Host "FAILED: $fail / $($report.Count)" -ForegroundColor Red
exit 1
