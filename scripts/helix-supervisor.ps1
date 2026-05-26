# 常駐スーパーバイザー — 60秒ごとに健全性確認・自動復旧
# install-stable.ps1 からタスク登録（ログオン後ずっと稼働）
param(
    [ValidateSet("lan", "tunnel", "both", "local")]
    [string]$Mode = "both",
    [int]$IntervalSec = 60
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
Set-Location $Root
. (Join-Path $Root "scripts\helix-core.ps1")

$dataDir = Join-Path $Root "data"
$null = New-Item -ItemType Directory -Force -Path $dataDir
$logFile = Join-Path $dataDir "supervisor.log"
$checkTunnel = $Mode -in @("tunnel", "both")

function Write-SuperLog {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $logFile -Value $line -Encoding UTF8
}

Write-SuperLog "===== supervisor started (mode=$Mode interval=${IntervalSec}s) ====="

# 初回はフル起動（再起動直後の立ち上げを確実に）
if (-not (Enter-HelixStartLock -Root $Root -WaitSec 240)) {
    Write-SuperLog "Could not acquire lock for initial start — exiting"
    exit 1
}
try {
    Invoke-HelixEnsureStack -Root $Root -Mode $Mode -SkipCollector
} finally {
    Exit-HelixStartLock -Root $Root
}

$okStreak = 0
$tunnelFailStreak = 0
$auditCounter = 0
$lastPublicUrl = $null
$tunnelHistory = Join-Path $dataDir "tunnel-history.jsonl"
while ($true) {
    Start-Sleep -Seconds $IntervalSec
    $auditCounter++
    if ($auditCounter % 60 -eq 0) {
        Remove-StaleHelixProcesses -Root $Root -Log { param($m) Write-SuperLog $m }
        & (Join-Path $Root "scripts\stability-metrics.ps1") -Root $Root
    }
    try {
        . (Join-Path $Root "scripts\public-url-helper.ps1")
        $jsonPath = Get-PublicUrlJsonPath $Root
        if (Test-Path $jsonPath) {
            $m = Get-Content $jsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
            $cur = [string]$m.public_url
            if ($cur -and $cur -ne $lastPublicUrl) {
                if ($lastPublicUrl) {
                    $ev = @{ ts = (Get-Date).ToString("o"); from = $lastPublicUrl; to = $cur } | ConvertTo-Json -Compress
                    Add-Content -Path $tunnelHistory -Value $ev -Encoding UTF8
                    Write-SuperLog "Public URL changed — see data/tunnel-history.jsonl"
                }
                $lastPublicUrl = $cur
            }
        }
    } catch { }
    $health = Test-HelixStackHealthy -Root $Root -CheckTunnel:$checkTunnel
    if ($health.Ok) {
        $okStreak++
        $tunnelFailStreak = 0
        if ($okStreak -eq 1 -or ($okStreak % 30) -eq 0) {
            Write-SuperLog "OK api=$($health.Api) ui=$($health.Ui) tunnel=$($health.Tunnel)"
        }
        continue
    }
    $okStreak = 0
    if ($health.Api -and $health.Ui -and -not $health.Tunnel -and $checkTunnel) {
        $tunnelFailStreak++
        if ($tunnelFailStreak -lt 2) {
            Write-SuperLog "Tunnel check failed once — waiting ($tunnelFailStreak/2)"
            continue
        }
        Write-SuperLog "Tunnel unhealthy — tunnel-only repair"
        if (Enter-HelixStartLock -Root $Root -WaitSec 60) {
            try {
                Invoke-HelixRepairTunnel -Root $Root -Mode $Mode
            } finally {
                Exit-HelixStartLock -Root $Root
            }
        }
        $tunnelFailStreak = 0
        continue
    }
    $tunnelFailStreak = 0
    Write-SuperLog "UNHEALTHY api=$($health.Api) ui=$($health.Ui) tunnel=$($health.Tunnel) — full repair"
    if (-not (Enter-HelixStartLock -Root $Root -WaitSec 120)) {
        Write-SuperLog "Repair skipped — lock held by another process"
        continue
    }
    try {
        Invoke-HelixEnsureStack -Root $Root -Mode $Mode -RepairOnly -SkipCollector
    } finally {
        Exit-HelixStartLock -Root $Root
    }
    $after = Test-HelixStackHealthy -Root $Root -CheckTunnel:$checkTunnel
    Write-SuperLog "After repair ok=$($after.Ok) api=$($after.Api) ui=$($after.Ui) tunnel=$($after.Tunnel)"
}
