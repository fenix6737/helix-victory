# Helix Victory — PCログオン時に自動起動（タスクスケジューラから実行）
# 手動: .\scripts\helix-autostart.ps1
param(
    [ValidateSet("lan", "tunnel", "both", "local")]
    [string]$Mode = "both",
    [switch]$SkipTunnel,
    [switch]$SkipCollector,
    [switch]$RepairOnly,
    [switch]$TunnelOnly
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
Set-Location $Root
. (Join-Path $Root "scripts\helix-core.ps1")

$dataDir = Join-Path $Root "data"
$null = New-Item -ItemType Directory -Force -Path $dataDir
$logFile = Join-Path $dataDir "autostart.log"
$urlFile = Join-Path $dataDir "public-url.txt"
$tunnelLog = Join-Path $dataDir "cloudflared.log"
$cfBin = Join-Path $Root "scripts\bin\cloudflared.exe"
$pidFile = Join-Path $dataDir "autostart.pids.json"

function Write-Log {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $logFile -Value $line -Encoding UTF8
}

function Test-HttpOk {
    param([string]$Url)
    try {
        $code = & curl.exe -s -o NUL -w "%{http_code}" --max-time 8 $Url 2>$null
        return $code -eq "200"
    } catch {
        return $false
    }
}

function Test-HttpStatus {
    param([string]$Url)
    try {
        return (& curl.exe -s -o NUL -w "%{http_code}" --max-time 8 $Url 2>$null)
    } catch {
        return "000"
    }
}

function Test-PortUp {
    param([int]$Port)
    return $null -ne (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1)
}

function Get-LanIPv4 {
    $ip = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.IPAddress -notmatch "^127\." -and
            $_.PrefixOrigin -ne "WellKnown" -and
            $_.InterfaceAlias -notmatch "vEthernet|WSL|Loopback"
        } |
        Sort-Object InterfaceMetric |
        Select-Object -First 1 -ExpandProperty IPAddress
    return $ip
}

function Get-PyExe {
    if (Get-Command py -ErrorAction SilentlyContinue) { return @{ File = "py"; Args = @("-3.12") } }
    if (Test-Path "C:\Python312\python.exe") { return @{ File = "C:\Python312\python.exe"; Args = @() } }
    return @{ File = "python"; Args = @() }
}

function Get-SqliteDatabaseUrl {
    $db = Join-Path $Root "backend\helix_local.db"
    $uri = "sqlite+aiosqlite:///" + ($db -replace "\\", "/")
    return $uri
}

function Test-PostgresUp {
    return $null -ne (Get-NetTCPConnection -LocalPort 5432 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1)
}

function Start-HelixApi {
    if (Test-PortUp 8000) {
        if (Test-HttpOk "http://127.0.0.1:8000/health") {
            Write-Log "API already running on :8000"
            return $true
        }
        Stop-PortListener -Port 8000
        Start-Sleep -Seconds 3
    }
    $py = Get-PyExe
    $useSqlite = $true
    if ($env:HELIX_USE_POSTGRES -eq "1" -and (Wait-PostgresReady -MaxSec 60)) {
        $useSqlite = $false
    }
    if ($useSqlite) {
        Write-Log "API using SQLite (helix_local.db) for stable autostart"
    }
    Write-Log "Starting API on 0.0.0.0:8000"
    $backend = Join-Path $Root "backend"
    $apiLog = Join-Path $dataDir "api.log"
    if ($useSqlite) {
        $sqliteUrl = Get-SqliteDatabaseUrl
        $argLine = ($py.Args + @("-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000")) -join " "
        $cmd = "set DATABASE_URL=$sqliteUrl&& `"$($py.File)`" $argLine >> `"$apiLog`" 2>&1"
        Start-Process -WindowStyle Hidden -FilePath "cmd.exe" `
            -ArgumentList @("/c", $cmd) -WorkingDirectory $backend
    } else {
        $argLine = ($py.Args + @("-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000")) -join " "
        $cmd = "`"$($py.File)`" $argLine >> `"$apiLog`" 2>&1"
        Start-Process -WindowStyle Hidden -FilePath "cmd.exe" `
            -ArgumentList @("/c", $cmd) -WorkingDirectory $backend
    }
    for ($i = 0; $i -lt 90; $i++) {
        if (Test-HttpOk "http://127.0.0.1:8000/health") { return $true }
        Start-Sleep -Seconds 2
    }
    Write-Log "API failed to become healthy — see data/api.log"
    return $false
}

function Test-CollectorRunning {
    return (@(Get-HelixCollectorProcesses).Count -gt 0)
}

function Start-HelixCollector {
    if ($SkipCollector) {
        Write-Log "Collector skipped"
        return
    }
    Remove-DuplicateCollectors -Log { param($m) Write-Log $m }
    if (Test-CollectorRunning) {
        Write-Log "Collector daemon already running"
        return
    }
    $py = Get-PyExe
    Write-Log "Starting collector daemon"
    Start-Process -WindowStyle Hidden -FilePath $py.File `
        -ArgumentList ($py.Args + @("-m", "collector.daemon", "--stores", "kicona_amagasaki,maruhan_umeda")) `
        -WorkingDirectory (Join-Path $Root "collector")
}

function Start-PeriodicAnalysisOnce {
    if (@(Get-HelixAnalysisLoopProcesses).Count -gt 0) {
        Write-Log "Periodic analysis loop already running"
        return
    }
    $loopScript = Join-Path $Root "scripts\analysis-loop.ps1"
    $marker = Join-Path $dataDir "analysis-loop.json"
    $p = Start-Process -WindowStyle Hidden -FilePath "powershell.exe" `
        -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $loopScript) `
        -WorkingDirectory $Root -PassThru
    @{ pid = $p.Id; started_at = (Get-Date).ToUniversalTime().ToString("o") } |
        ConvertTo-Json | Set-Content -Path $marker -Encoding UTF8
    Write-Log "Periodic analysis loop started (pid=$($p.Id), every 2h)"
}

function Stop-PortListener {
    param([int]$Port)
    $pids = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique)
    foreach ($pid in $pids) {
        if ($pid -and $pid -gt 0) {
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Write-Log "Stopped process $pid on port $Port"
        }
    }
}

function Start-HelixFrontend {
    if (Test-PortUp 3000) {
        $code = Test-HttpStatus "http://127.0.0.1:3000/welcome"
        if ($code -eq "200") {
            Write-Log "Frontend already running on :3000"
            return $true
        }
        Write-Log "Port 3000 unhealthy (HTTP $code) — restarting frontend"
        Stop-HelixFrontendProcesses
        Stop-PortListener -Port 3000
        Start-Sleep -Seconds 3
    }
    Write-Log "Starting frontend on 0.0.0.0:3000"
    $useProdPre = Test-HelixFrontendProductionReady -Root $Root
    if ($useProdPre -and $env:HELIX_FORCE_DEV_UI -ne "1") {
        $chunkDir = Join-Path $Root "frontend\.next\static\chunks"
        if (-not (Test-Path $chunkDir) -or -not (@(Get-ChildItem $chunkDir -Filter "*.js" -EA SilentlyContinue).Count -gt 0)) {
            Write-Log "Production .next incomplete — falling back to dev:public"
            $useProdPre = $false
        }
    }
    $npm = (Get-Command npm -ErrorAction SilentlyContinue).Source
    if (-not $npm) {
        Write-Log "npm not found in PATH"
        return $false
    }
    $useProd = $useProdPre
    if ($env:HELIX_FORCE_DEV_UI -eq "1") {
        $useProd = $false
    }
    $npmScript = if ($useProd) { "start:public" } else { "dev:public" }
    Write-Log "Frontend mode: $npmScript"
    $feLog = Join-Path $dataDir "frontend.log"
    $feDir = Join-Path $Root "frontend"
    $cmd = "npm run $npmScript >> `"$feLog`" 2>&1"
    Start-Process -WindowStyle Hidden -FilePath "cmd.exe" `
        -ArgumentList @("/c", $cmd) -WorkingDirectory $feDir
    for ($i = 0; $i -lt 120; $i++) {
        if (Test-HttpOk "http://127.0.0.1:3000/welcome") { return $true }
        Start-Sleep -Seconds 2
    }
    Write-Log "Frontend failed to become healthy — see data/frontend.log"
    return $false
}

function Get-CloudflaredExe {
    if (Get-Command cloudflared -ErrorAction SilentlyContinue) { return "cloudflared" }
    if (Test-Path $cfBin) { return $cfBin }
    try {
        New-Item -ItemType Directory -Force -Path (Split-Path $cfBin) | Out-Null
        Invoke-WebRequest -Uri "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" `
            -OutFile $cfBin -UseBasicParsing
        return $cfBin
    } catch {
        Write-Log "cloudflared download failed: $($_.Exception.Message)"
        return $null
    }
}

function Get-TunnelUrlFromLog {
    $parts = @()
    if (Test-Path $tunnelLog) { $parts += Get-Content $tunnelLog -Raw -ErrorAction SilentlyContinue }
    $errLog = "$tunnelLog.err"
    if (Test-Path $errLog) { $parts += Get-Content $errLog -Raw -ErrorAction SilentlyContinue }
    $text = $parts -join "`n"
    if ($text -match "(https://[a-z0-9-]+\.trycloudflare\.com)") { return $Matches[1] }
    return $null
}

function Start-HelixTunnel {
    if (-not (Test-HttpOk "http://127.0.0.1:3000/welcome")) {
        Write-Log "Tunnel skipped — frontend not healthy on :3000"
        return $null
    }
    . (Join-Path $Root "scripts\cloudflared-fixed.ps1")
    . (Join-Path $Root "scripts\public-url-helper.ps1")
    if (Test-FixedTunnelConfigured $Root) {
        return Start-FixedCloudflaredTunnel -Root $Root -Log { param($m) Write-Log $m }
    }
    $cloud = Get-EnvPublicBaseUrl $Root
    if ($cloud -and (Test-PublicBaseUrlReachable $cloud)) {
        Write-Log "Using reachable cloud URL from .env (no PC tunnel): $cloud"
        return $cloud
    }
    if ($cloud) {
        Write-Log ".env URL not reachable ($cloud) — starting quick tunnel"
    }
    Stop-CloudflaredProcesses -Log { param($m) Write-Log $m }
    return Start-QuickCloudflaredTunnel -Root $Root -TunnelLog $tunnelLog -Log { param($m) Write-Log $m }
}

function Update-PublicUrlFile {
    param([string]$TunnelUrl, [string]$LanIp)
    . (Join-Path $Root "scripts\cloudflared-fixed.ps1")
    $fixed = Get-FixedPublicBaseUrl $Root
    if ($fixed) {
        Update-PublicUrlFileFixed -Root $Root -PublicBaseUrl $fixed -LanIp $LanIp
        return
    }
    $cloud = Get-EnvPublicBaseUrl $Root
    if ($cloud) {
        Update-PublicUrlFileFree -Root $Root -PublicBaseUrl $cloud -LanIp $LanIp -Mode "cloud"
        return
    }
    if ($TunnelUrl) {
        Update-PublicUrlFileFree -Root $Root -PublicBaseUrl $TunnelUrl -LanIp $LanIp -Mode "quick"
        return
    }
    $lines = @(
        "Helix Victory — public access",
        "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
        "",
        "トンネル未起動 — Local: http://127.0.0.1:3000/welcome",
        "固定無料: docs/DEPLOY_FREE_24x7.md",
        "Log: data/autostart.log"
    )
    Set-Content -Path $urlFile -Value ($lines -join "`n") -Encoding UTF8
}

# --- main ---
if (-not $RepairOnly) {
    if (-not (Enter-HelixStartLock -Root $Root -WaitSec 240)) {
        Write-Log "Another autostart in progress — exiting"
        exit 0
    }
}

try {
Write-Log "===== autostart begin (mode=$Mode repair=$RepairOnly tunnelOnly=$TunnelOnly) ====="

foreach ($lf in @($logFile, (Join-Path $dataDir "api.log"), (Join-Path $dataDir "frontend.log"))) {
    Rotate-HelixLogFile -Path $lf -MaxMb 8
}
Rotate-HelixLogFile -Path (Join-Path $dataDir "supervisor.log") -MaxMb 5

if (-not $RepairOnly -and -not $TunnelOnly) {
    Remove-StaleHelixProcesses -Root $Root -Log { param($m) Write-Log $m }
}

if ($TunnelOnly) {
    if (-not (Test-HttpOk "http://127.0.0.1:3000/welcome")) {
        Write-Log "Tunnel-only repair skipped — UI not healthy"
    } else {
        . (Join-Path $Root "scripts\cloudflared-fixed.ps1")
        . (Join-Path $Root "scripts\public-url-helper.ps1")
        $tunnelUrl = Start-HelixTunnel
        $lan = Get-LanIPv4
        Update-PublicUrlFile -TunnelUrl $tunnelUrl -LanIp $lan
        if ($tunnelUrl) {
            Save-PublicUrlManifest -Root $Root -PublicBaseUrl $tunnelUrl -LanIp $lan -Mode "quick" -Source "tunnel-repair"
            Write-Log "Tunnel-only repair done url=$tunnelUrl"
        }
    }
    Write-Log "autostart done (tunnel-only)"
    return
}

if ($RepairOnly) {
    $health = Test-HelixStackHealthy -Root $Root -CheckTunnel:($Mode -in @("tunnel", "both") -and -not $SkipTunnel)
    if ($health.Api -and $health.Ui -and (-not ($Mode -in @("tunnel", "both")) -or $SkipTunnel -or $health.Tunnel)) {
        Write-Log "Repair skipped — stack healthy"
        exit 0
    }
    Start-Sleep -Seconds 2
} else {
    Start-Sleep -Seconds 15
    Wait-HelixNetwork -MaxSec 90 -Log { param($m) Write-Log $m }
}

if (-not $RepairOnly -and (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Log "Starting docker redis/postgres if available"
    try {
        docker compose -f (Join-Path $Root "docker-compose.yml") up -d redis postgres 2>&1 | Out-Null
        Start-Sleep -Seconds 3
    } catch {
        Write-Log "docker compose skipped"
    }
}

$apiOk = Start-HelixApi
if (-not $RepairOnly -and -not $SkipCollector) {
    Start-HelixCollector
}
$uiOk = Start-HelixFrontend

if (-not $apiOk -or -not $uiOk) {
    for ($round = 1; $round -le 3; $round++) {
        if ($apiOk -and $uiOk) { break }
        Write-Log "Retry round $round/3 in 45s..."
        Start-Sleep -Seconds 45
        if (-not $apiOk) {
            Stop-PortListener -Port 8000
            Start-Sleep -Seconds 2
            $apiOk = Start-HelixApi
        }
        if (-not $uiOk) {
            Stop-PortListener -Port 3000
            Start-Sleep -Seconds 2
            $uiOk = Start-HelixFrontend
        }
    }
}

$tunnelUrl = $null
$useTunnel = -not $SkipTunnel -and $Mode -in @("tunnel", "both")
if ($useTunnel -and $uiOk) {
    $tunnelUrl = Start-HelixTunnel
}

$lan = Get-LanIPv4
Update-PublicUrlFile -TunnelUrl $tunnelUrl -LanIp $lan

. (Join-Path $Root "scripts\public-url-helper.ps1")
. (Join-Path $Root "scripts\cloudflared-fixed.ps1")
$manifestUrl = $null
$manifestMode = "quick"
if ($tunnelUrl) {
    $manifestUrl = $tunnelUrl
    $manifestMode = if ($tunnelUrl -match "trycloudflare") { "quick" } else { "fixed" }
} else {
    $fixed = Get-FixedPublicBaseUrl $Root
    if ($fixed) {
        $manifestUrl = $fixed
        $manifestMode = "fixed"
    } else {
        $cloud = Get-EnvPublicBaseUrl $Root
        if ($cloud -and (Test-PublicBaseUrlReachable $cloud)) {
            $manifestUrl = $cloud
            $manifestMode = "cloud"
        }
    }
}
if ($manifestUrl) {
    Save-PublicUrlManifest -Root $Root -PublicBaseUrl $manifestUrl -LanIp $lan -Mode $manifestMode -Source "autostart"
    Show-PublicUrlToast -WelcomeUrl "$($manifestUrl.TrimEnd('/'))/welcome"
    Write-Log "Public URL saved — data/public-url.txt / Desktop shortcut"
} else {
    Write-Log "No public URL yet — retry or run Start Helix Victory.bat"
}

if (-not $RepairOnly) {
    Start-PeriodicAnalysisOnce
}

Write-Log "autostart done api=$apiOk ui=$uiOk tunnel=$([bool]$tunnelUrl)"
} finally {
    if (-not $RepairOnly) {
        Exit-HelixStartLock -Root $Root
    }
}
exit 0
