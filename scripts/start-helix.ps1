# Helix Victory - one-click start (API/UI/tunnel + browser)
param(
    [ValidateSet("lan", "tunnel", "both", "local")]
    [string]$Mode = "both",
    [switch]$SkipTunnel,
    [switch]$NoDialog
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
Set-Location $Root

. (Join-Path $Root "scripts\helix-core.ps1")
. (Join-Path $Root "scripts\public-url-helper.ps1")

Write-Host "Starting Helix Victory..." -ForegroundColor Cyan

& (Join-Path $Root "scripts\helix-autostart.ps1") -Mode $Mode -SkipTunnel:$SkipTunnel *>&1 | Out-Null

$jsonPath = Get-PublicUrlJsonPath $Root
$welcomeLocal = "http://127.0.0.1:3000/welcome"

Write-Host "Waiting for API and UI..." -ForegroundColor DarkGray
$ready = $false
for ($i = 0; $i -lt 90; $i++) {
    $checkTunnel = (-not $SkipTunnel) -and ($Mode -in @("tunnel", "both"))
    $h = Test-HelixStackHealthy -Root $Root -CheckTunnel:$checkTunnel
    if ($h.Api -and $h.Ui) {
        $ready = $true
        break
    }
    Start-Sleep -Seconds 2
}

if (-not $ready) {
    Write-Host "UI/API did not start. Check data\frontend.log and data\api.log" -ForegroundColor Red
    if (-not $NoDialog) { pause }
    exit 1
}

for ($i = 0; $i -lt 15; $i++) {
    if ((Test-Path $jsonPath) -and (Get-Content $jsonPath -Raw -Encoding UTF8) -match "trycloudflare|fly\.dev") {
        break
    }
    Start-Sleep -Seconds 2
    $tunnelLog = Join-Path $Root "data\cloudflared.log"
    if (Test-Path $tunnelLog) {
        $text = Get-Content $tunnelLog -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
        if ($text -match "(https://[a-z0-9-]+\.trycloudflare\.com)") {
            $url = $Matches[1]
            . (Join-Path $Root "scripts\cloudflared-fixed.ps1")
            $lan = (Get-NetIPAddress -AddressFamily IPv4 -EA SilentlyContinue |
                Where-Object { $_.IPAddress -notmatch "^127\." -and $_.InterfaceAlias -notmatch "vEthernet|WSL" } |
                Select-Object -First 1 -ExpandProperty IPAddress)
            Update-PublicUrlFileFree -Root $Root -PublicBaseUrl $url -LanIp $lan -Mode "quick"
            Save-PublicUrlManifest -Root $Root -PublicBaseUrl $url -LanIp $lan -Mode "quick" -Source "start-helix"
            break
        }
    }
}

try { Start-Process $welcomeLocal } catch { }

if (-not $NoDialog) {
    $null = Show-PublicUrlToUser -Root $Root
} else {
    if (Test-Path $jsonPath) {
        $m = Get-Content $jsonPath -Raw -Encoding UTF8 -ErrorAction SilentlyContinue | ConvertFrom-Json
        if ($m.welcome_url) { Show-PublicUrlToast -WelcomeUrl $m.welcome_url }
    }
}

Write-Host ""
Write-Host ("Local: {0}" -f $welcomeLocal) -ForegroundColor Green
if (Test-Path $jsonPath) {
    $m = Get-Content $jsonPath -Raw -Encoding UTF8 -ErrorAction SilentlyContinue | ConvertFrom-Json
    if ($m.welcome_url) {
        Write-Host ("Public URL: {0}" -f $m.welcome_url) -ForegroundColor Cyan
    }
}
exit 0
