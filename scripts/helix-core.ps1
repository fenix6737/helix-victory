# Shared health / lock for Helix autostart / supervisor
param()

function Get-HelixRootFromScript {
    param([string]$ScriptPath)
    Split-Path -Parent $ScriptPath | Split-Path -Parent
}

function Get-HelixLockPath {
    param([string]$Root)
    Join-Path $Root "data\helix-start.lock"
}

function Enter-HelixStartLock {
    param(
        [string]$Root,
        [int]$WaitSec = 180
    )
    $lockPath = Get-HelixLockPath $Root
    $dataDir = Split-Path $lockPath -Parent
    if (-not (Test-Path $dataDir)) {
        New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
    }
    for ($i = 0; $i -lt $WaitSec; $i++) {
        try {
            $fs = [System.IO.File]::Open($lockPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
            $fs.Close()
            return $true
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    return $false
}

function Exit-HelixStartLock {
    param([string]$Root)
    $lockPath = Get-HelixLockPath $Root
    if (Test-Path $lockPath) {
        Remove-Item $lockPath -Force -ErrorAction SilentlyContinue
    }
}

function Wait-HelixNetwork {
    param(
        [int]$MaxSec = 120,
        [scriptblock]$Log = { param($m) }
    )
    for ($i = 0; $i -lt $MaxSec; $i += 3) {
        try {
            if (Test-Connection -ComputerName 1.1.1.1 -Count 1 -Quiet -ErrorAction Stop) {
                & $Log "Network ready"
                return $true
            }
        } catch { }
        Start-Sleep -Seconds 3
    }
    & $Log "Network wait timeout — continuing anyway"
    return $false
}

function Wait-PostgresReady {
    param([int]$MaxSec = 45)
    $loops = [math]::Ceiling($MaxSec / 2)
    for ($i = 0; $i -lt $loops; $i++) {
        $up = $null -ne (Get-NetTCPConnection -LocalPort 5432 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1)
        if ($up) { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Stop-CloudflaredProcesses {
    param([scriptblock]$Log = { param($m) })
    Get-Process cloudflared -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        & $Log "Stopped cloudflared pid $($_.Id)"
    }
}

function Stop-HelixFrontendProcesses {
    Get-Process node,cmd -ErrorAction SilentlyContinue | ForEach-Object {
        try {
            $c = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue).CommandLine
            if ($c -match "next|npm run (dev:public|start:public)|helix-victory-frontend") {
                Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
            }
        } catch { }
    }
    Start-Sleep -Seconds 2
}

function Test-HelixFrontendProductionReady {
    param([string]$Root)
    Test-Path (Join-Path $Root "frontend\.next\BUILD_ID")
}

function Test-HelixStackHealthy {
    param(
        [string]$Root,
        [switch]$CheckTunnel
    )
    . (Join-Path $Root "scripts\public-url-helper.ps1")
    $api = $false
    $ui = $false
    try {
        $apiCode = & curl.exe -s -o NUL -w "%{http_code}" --max-time 8 "http://127.0.0.1:8000/health" 2>$null
        $api = $apiCode -eq "200"
    } catch { }
    try {
        $uiCode = & curl.exe -s -o NUL -w "%{http_code}" --max-time 8 "http://127.0.0.1:3000/welcome" 2>$null
        $ui = $uiCode -eq "200"
    } catch { }
    $tunnel = $true
    if ($CheckTunnel) {
        $tunnel = $false
        $jsonPath = Get-PublicUrlJsonPath $Root
        if (Test-Path $jsonPath) {
            try {
                $m = Get-Content $jsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
                $welcome = [string]$m.welcome_url
                $base = $welcome -replace "/welcome$", ""
                if ($base -and (Test-PublicBaseUrlReachable $base)) {
                    $tunnel = $true
                }
            } catch { }
        }
        if (-not $tunnel) {
            $tunnelLog = Join-Path $Root "data\cloudflared.log"
            $parts = @()
            if (Test-Path $tunnelLog) { $parts += Get-Content $tunnelLog -Raw -EA SilentlyContinue }
            if (Test-Path "$tunnelLog.err") { $parts += Get-Content "$tunnelLog.err" -Raw -EA SilentlyContinue }
            if (($parts -join "`n") -match "(https://[a-z0-9-]+\.trycloudflare\.com)") {
                $tunnel = Test-PublicBaseUrlReachable $Matches[1]
            }
        }
    }
    return @{ Api = $api; Ui = $ui; Tunnel = $tunnel; Ok = ($api -and $ui -and (-not $CheckTunnel -or $tunnel)) }
}

function Rotate-HelixLogFile {
    param(
        [string]$Path,
        [double]$MaxMb = 5
    )
    if (-not (Test-Path $Path)) { return }
    $sizeMb = (Get-Item $Path).Length / 1MB
    if ($sizeMb -lt $MaxMb) { return }
    $bak = "$Path.$((Get-Date -Format 'yyyyMMdd-HHmmss')).old"
    Move-Item -Path $Path -Destination $bak -Force -ErrorAction SilentlyContinue
}

function Get-HelixAnalysisLoopProcesses {
    @(Get-CimInstance Win32_Process -EA SilentlyContinue |
        Where-Object { $_.CommandLine -match "analysis-loop\.ps1" })
}

function Get-HelixCollectorProcesses {
    @(Get-CimInstance Win32_Process -EA SilentlyContinue |
        Where-Object {
            $_.CommandLine -match "collector\.daemon" -and
            $_.Name -match "^python(\d+)?\.exe$"
        })
}

function Remove-DuplicateCollectors {
    param([scriptblock]$Log = { param($m) })
    $collectorProcs = @(Get-HelixCollectorProcesses)
    if ($collectorProcs.Count -le 1) { return }
    $sorted = $collectorProcs | Sort-Object CreationDate -Descending
    foreach ($p in $sorted | Select-Object -Skip 1) {
        Stop-Process -Id $p.ProcessId -Force -EA SilentlyContinue
        & $Log "Stopped duplicate collector pid $($p.ProcessId)"
    }
}

function Remove-StaleHelixProcesses {
    param(
        [string]$Root,
        [scriptblock]$Log = { param($m) }
    )
    Remove-DuplicateCollectors -Log $Log
    $healthy3000 = $false
    try {
        $c = curl.exe -s -o NUL -w "%{http_code}" --max-time 5 "http://127.0.0.1:3000/welcome" 2>$null
        $healthy3000 = $c -eq "200"
    } catch { }
    if (-not $healthy3000) {
        $pids = @(Get-NetTCPConnection -LocalPort 3000 -State Listen -EA SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique)
        foreach ($pid in $pids) {
            if ($pid -gt 0) {
                Stop-Process -Id $pid -Force -EA SilentlyContinue
                & $Log "Stopped stale frontend pid $pid"
            }
        }
    }
    $cfCount = @(Get-Process cloudflared -EA SilentlyContinue).Count
    if ($cfCount -gt 1) {
        Stop-CloudflaredProcesses -Log $Log
        & $Log "Cleared $cfCount cloudflared instances (will restart if needed)"
    }
}

function Invoke-HelixEnsureStack {
    param(
        [string]$Root,
        [ValidateSet("lan", "tunnel", "both", "local")]
        [string]$Mode = "both",
        [switch]$RepairOnly,
        [switch]$TunnelOnly,
        [switch]$SkipCollector,
        [switch]$SkipTunnel
    )
    $args = @{
        Mode          = $Mode
        RepairOnly    = $RepairOnly
        TunnelOnly    = $TunnelOnly
        SkipCollector = $SkipCollector
        SkipTunnel    = $SkipTunnel
    }
    & (Join-Path $Root "scripts\helix-autostart.ps1") @args
}

function Invoke-HelixRepairTunnel {
    param(
        [string]$Root,
        [ValidateSet("lan", "tunnel", "both", "local")]
        [string]$Mode = "both"
    )
    Invoke-HelixEnsureStack -Root $Root -Mode $Mode -RepairOnly -TunnelOnly -SkipCollector
}
