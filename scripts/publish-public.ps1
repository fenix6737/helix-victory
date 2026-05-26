# Helix Victory — public access (LAN + Cloudflare quick tunnel)
# Usage:
#   .\scripts\publish-public.ps1              # tunnel (internet) + LAN URLs
#   .\scripts\publish-public.ps1 -Mode lan    # same Wi-Fi only
#   .\scripts\publish-public.ps1 -Mode tunnel # internet only
param(
    [ValidateSet("lan", "tunnel", "both")]
    [string]$Mode = "both"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
Set-Location $Root

$dataDir = Join-Path $Root "data"
$null = New-Item -ItemType Directory -Force -Path $dataDir
$urlFile = Join-Path $dataDir "public-url.txt"
$tunnelLog = Join-Path $dataDir "cloudflared.log"
$cfBin = Join-Path $Root "scripts\bin\cloudflared.exe"

function Get-LanIPv4 {
    $ip = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.IPAddress -notmatch "^127\." -and
            $_.PrefixOrigin -ne "WellKnown" -and
            $_.InterfaceAlias -notmatch "vEthernet|WSL|Loopback"
        } |
        Sort-Object -Property InterfaceMetric |
        Select-Object -First 1 -ExpandProperty IPAddress
    if ($ip) { return $ip }
    return $null
}

function Ensure-FirewallRule {
    param([int]$Port, [string]$Name)
    try {
        $existing = Get-NetFirewallRule -DisplayName $Name -ErrorAction SilentlyContinue
        if (-not $existing) {
            New-NetFirewallRule -DisplayName $Name -Direction Inbound -LocalPort $Port -Protocol TCP -Action Allow -Profile Private,Domain | Out-Null
        }
    } catch {
        Write-Host "Firewall rule skipped (run as Admin for LAN): $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

function Stop-Port {
    param([int]$Port)
    $procId = (Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess
    if ($procId) {
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
}

function Update-EnvCors {
    param([string[]]$Origins)
    $envPath = Join-Path $Root ".env"
    if (-not (Test-Path $envPath)) { return }
    $line = "CORS_ORIGINS=" + ($Origins -join ",")
    $text = Get-Content $envPath -Raw -Encoding UTF8
    if ($text -match "(?m)^CORS_ORIGINS=.*$") {
        $text = [regex]::Replace($text, "(?m)^CORS_ORIGINS=.*$", $line)
    } else {
        $text += "`n$line`n"
    }
    if ($text -notmatch "(?m)^PUBLIC_ACCESS=") {
        $text += "PUBLIC_ACCESS=1`n"
    } else {
        $text = [regex]::Replace($text, "(?m)^PUBLIC_ACCESS=.*$", "PUBLIC_ACCESS=1")
    }
    if ($text -notmatch "(?m)^API_URL_INTERNAL=") {
        $text += "API_URL_INTERNAL=http://127.0.0.1:8000`n"
    }
    if ($text -notmatch "(?m)^HELIX_COOKIE_SECURE=") {
        $text += "HELIX_COOKIE_SECURE=1`n"
    } else {
        $text = [regex]::Replace($text, "(?m)^HELIX_COOKIE_SECURE=.*$", "HELIX_COOKIE_SECURE=1")
    }
    Set-Content -Path $envPath -Value $text.TrimEnd() -Encoding UTF8 -NoNewline
    Add-Content -Path $envPath -Value "`n" -Encoding UTF8
}

function Ensure-Cloudflared {
    if (Get-Command cloudflared -ErrorAction SilentlyContinue) {
        return "cloudflared"
    }
    if (Test-Path $cfBin) {
        return $cfBin
    }
    Write-Host "Downloading cloudflared..." -ForegroundColor Cyan
    $binDir = Split-Path $cfBin
    New-Item -ItemType Directory -Force -Path $binDir | Out-Null
    $url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    Invoke-WebRequest -Uri $url -OutFile $cfBin -UseBasicParsing
    return $cfBin
}

function Test-HttpOk {
    param([string]$Url)
    try {
        $code = & curl.exe -s -o NUL -w "%{http_code}" --max-time 5 $Url
        return $code -eq "200"
    } catch {
        return $false
    }
}

function Get-TunnelLogText {
    $parts = @()
    if (Test-Path $tunnelLog) { $parts += Get-Content $tunnelLog -Raw -ErrorAction SilentlyContinue }
    $errLog = "$tunnelLog.err"
    if (Test-Path $errLog) { $parts += Get-Content $errLog -Raw -ErrorAction SilentlyContinue }
    return ($parts -join "`n")
}

function Start-Tunnel {
    param([string]$CfExe)
    if (Test-Path $tunnelLog) { Remove-Item $tunnelLog -Force -ErrorAction SilentlyContinue }
    $errLog = "$tunnelLog.err"
    if (Test-Path $errLog) { Remove-Item $errLog -Force -ErrorAction SilentlyContinue }
    # cloudflared prints the trycloudflare URL on stderr
    $proc = Start-Process -FilePath $CfExe -PassThru -WindowStyle Hidden `
        -ArgumentList "tunnel", "--url", "http://127.0.0.1:3000", "--no-autoupdate" `
        -RedirectStandardOutput $tunnelLog -RedirectStandardError $errLog
    for ($i = 0; $i -lt 45; $i++) {
        Start-Sleep -Seconds 2
        $text = Get-TunnelLogText
        if ($text -match "(https://[a-z0-9-]+\.trycloudflare\.com)") {
            return @{ Url = $Matches[1]; ProcessId = $proc.Id }
        }
    }
    throw "Cloudflare tunnel URL not found. See $tunnelLog and $errLog"
}

$lanIp = Get-LanIPv4
$cors = @("http://localhost:3000", "http://127.0.0.1:3000")
if ($lanIp) { $cors += "http://${lanIp}:3000" }
Update-EnvCors -Origins $cors

if ($Mode -in @("lan", "both") -and $lanIp) {
    Ensure-FirewallRule -Port 3000 -Name "Helix Victory UI (3000)"
}

Stop-Port -Port 8000
Stop-Port -Port 3000

Write-Host "Starting API (0.0.0.0:8000)..." -ForegroundColor Cyan
Start-Process -WindowStyle Hidden -FilePath "py" `
    -ArgumentList "-3.12", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000" `
    -WorkingDirectory (Join-Path $Root "backend")

for ($i = 0; $i -lt 30; $i++) {
    if (Test-HttpOk "http://127.0.0.1:8000/health") { break }
    Start-Sleep -Seconds 1
}

Write-Host "Starting frontend (0.0.0.0:3000)..." -ForegroundColor Cyan
Start-Process -WindowStyle Hidden -FilePath "npm" `
    -ArgumentList "run", "dev:public" `
    -WorkingDirectory (Join-Path $Root "frontend")

for ($i = 0; $i -lt 45; $i++) {
    if (Test-HttpOk "http://127.0.0.1:3000/welcome") { break }
    Start-Sleep -Seconds 1
}

$lines = @()
$lines += "Helix Victory — public access"
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
$lines += ""

if ($Mode -in @("lan", "both") -and $lanIp) {
    $lanUi = "http://${lanIp}:3000"
    $lines += "LAN (same Wi-Fi):"
    $lines += "  Welcome: $lanUi/welcome"
    $lines += "  Login:   $lanUi/login"
    $lines += "  App:     $lanUi/"
    $lines += ""
}

if ($Mode -in @("tunnel", "both")) {
    . (Join-Path $Root "scripts\cloudflared-fixed.ps1")
    $tunnelUrl = $null
    if (Test-FixedTunnelConfigured $Root) {
        Write-Host "Starting fixed Cloudflare tunnel..." -ForegroundColor Cyan
        $tunnelUrl = Start-FixedCloudflaredTunnel -Root $Root
    } elseif (Get-EnvPublicBaseUrl $Root) {
        $tunnelUrl = Get-EnvPublicBaseUrl $Root
        Write-Host "Using cloud fixed URL from .env: $tunnelUrl" -ForegroundColor Cyan
    } else {
        Write-Host "Starting free quick tunnel (URL changes on reboot)..." -ForegroundColor Yellow
        $tunnelUrl = Start-QuickCloudflaredTunnel -Root $Root -TunnelLog $tunnelLog
    }
    if (-not $tunnelUrl) { exit 1 }
    $lines += "Internet (HTTPS):"
    $lines += "  Welcome: $tunnelUrl/welcome"
    $lines += "  Login:   $tunnelUrl/login"
    $lines += ""
}

$lines += "Admin: helix_admin (see .env ADMIN_PASSWORD)"
$lines += "Keep this PowerShell window PC on; tunnel stops when PC sleeps."

$out = $lines -join "`n"
Set-Content -Path $urlFile -Value $out -Encoding UTF8
Write-Host ""
Write-Host $out -ForegroundColor Green
Write-Host ""
Write-Host "Saved: $urlFile" -ForegroundColor Cyan
