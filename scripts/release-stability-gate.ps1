# リリース安定性ゲート — ビルド・単体・負荷・ソーク・再発防止確認
param(
    [string]$Root = (Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent),
    [double]$SoakHours = 3,
    [int]$SoakIntervalSec = 60,
    [switch]$SkipBuild,
    [switch]$SkipSoak,
    [switch]$RunSoakInBackground = $false
)

# 前景3時間ソークは release-stability-gate.ps1 -RunSoakInBackground でバックグラウンド化推奨

$ErrorActionPreference = "Continue"
$dataDir = Join-Path $Root "data"
$gateLog = Join-Path $dataDir "release-gate.log"
function Gate-Log($m) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $m
    Add-Content -Path $gateLog -Value $line -Encoding UTF8
    Write-Host $line
}

Gate-Log "===== release stability gate begin ====="

if (-not $SkipBuild) {
    Gate-Log "Building frontend (production)..."
    Push-Location (Join-Path $Root "frontend")
    try {
        if (-not (Test-Path "node_modules")) { npm ci 2>&1 | Out-Host }
        if (Test-Path ".next") { Remove-Item ".next" -Recurse -Force -ErrorAction SilentlyContinue }
        npm run build 2>&1 | Out-Host
        if (-not (Test-Path (Join-Path $Root "frontend\.next\BUILD_ID"))) {
            Gate-Log "FAIL npm run build — BUILD_ID missing"
            exit 1
        }
        Set-Content -Path (Join-Path $Root "data\stable-ui.flag") -Value "production" -Encoding UTF8
        Gate-Log "Frontend build OK"
    } finally {
        Pop-Location
    }
}

Gate-Log "Restarting frontend for production build..."
. (Join-Path $Root "scripts\helix-core.ps1")
Stop-HelixFrontendProcesses
$p3000 = @(Get-NetTCPConnection -LocalPort 3000 -State Listen -EA SilentlyContinue |
    Select-Object -Expand OwningProcess -Unique)
foreach ($procId in $p3000) {
    if ($procId -gt 0) { Stop-Process -Id $procId -Force -EA SilentlyContinue }
}
Start-Sleep -Seconds 3
Gate-Log "Ensuring stack (full autostart)..."
& (Join-Path $Root "scripts\helix-autostart.ps1") -Mode both 2>&1 | Out-Null
Start-Sleep -Seconds 8

Gate-Log "final-system-test..."
& (Join-Path $Root "scripts\final-system-test.ps1") -Root $Root -SkipTunnel
if ($LASTEXITCODE -ne 0) { Gate-Log "FAIL final-system-test"; exit 1 }

Gate-Log "verify-recurrence (pre-soak)..."
& (Join-Path $Root "scripts\verify-recurrence-prevention.ps1") -Root $Root -Phase "pre-gate"
# pre-gate may fail on soak/load — continue

Gate-Log "load-test..."
& (Join-Path $Root "scripts\load-test.ps1") -Root $Root
if ($LASTEXITCODE -ne 0) { Gate-Log "FAIL load-test"; exit 1 }

if ($SkipSoak) {
    Gate-Log "Soak skipped"
    exit 0
}

$soakScript = Join-Path $Root "scripts\soak-test.ps1"
if ($RunSoakInBackground) {
    $soakOut = Join-Path $dataDir "soak-run.log"
    Gate-Log "Starting soak ${SoakHours}h in background -> $soakOut"
    Start-Process -WindowStyle Hidden -FilePath "powershell.exe" `
        -ArgumentList @(
            "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", $soakScript,
            "-Root", $Root,
            "-Hours", $SoakHours,
            "-IntervalSec", $SoakIntervalSec
        ) -WorkingDirectory $Root `
        -RedirectStandardOutput $soakOut -RedirectStandardError $soakOut
    Gate-Log "Soak PID started — after completion run: verify-recurrence-prevention.ps1 -RequireSoakPass -RequireLoadPass"
    exit 0
}

Gate-Log "soak-test ${SoakHours}h (foreground)..."
& $soakScript -Root $Root -Hours $SoakHours -IntervalSec $SoakIntervalSec
if ($LASTEXITCODE -ne 0) { Gate-Log "FAIL soak-test"; exit 1 }

Gate-Log "verify-recurrence (post-gate)..."
& (Join-Path $Root "scripts\verify-recurrence-prevention.ps1") -Root $Root -Phase "post-gate" -RequireSoakPass -RequireLoadPass
if ($LASTEXITCODE -ne 0) { Gate-Log "FAIL recurrence prevention"; exit 1 }

Gate-Log "===== PASS release stability gate ====="
exit 0
