# 固定URLを1回セットアップ — 以降 PC再起動しても同じURL
# 要: Cloudflareアカウント + Cloudflareに登録済みドメイン
# Usage:
#   .\scripts\install-fixed-tunnel.ps1 -Hostname helix.あなたのドメイン.com
param(
    [Parameter(Mandatory = $true)]
    [string]$Hostname,
    [string]$TunnelName = "helix-victory"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
Set-Location $Root

. (Join-Path $Root "scripts\cloudflared-fixed.ps1")

$cf = Get-CloudflaredExePath $Root
if (-not $cf) {
    $binDir = Join-Path $Root "scripts\bin"
    New-Item -ItemType Directory -Force -Path $binDir | Out-Null
    $cf = Join-Path $binDir "cloudflared.exe"
    Write-Host "Downloading cloudflared..." -ForegroundColor Cyan
    Invoke-WebRequest -Uri "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" `
        -OutFile $cf -UseBasicParsing
}

$dataDir = Join-Path $Root "data\cloudflared"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

$Hostname = $Hostname.Trim().ToLower()
if ($Hostname -match "^https?://") {
    $Hostname = ($Hostname -replace "^https?://", "").TrimEnd("/")
}

Write-Host "=== Helix Victory — 固定URLセットアップ ===" -ForegroundColor Cyan
Write-Host "Hostname: $Hostname"
Write-Host ""

Write-Host "[1/5] Cloudflare ログイン（ブラウザ）..." -ForegroundColor Yellow
& $cf tunnel login
if ($LASTEXITCODE -ne 0) { throw "cloudflared tunnel login failed" }

Write-Host "[2/5] トンネル作成/確認: $TunnelName" -ForegroundColor Yellow
$listJson = & $cf tunnel list -o json 2>$null
$tunnelId = $null
if ($listJson) {
    $list = $listJson | ConvertFrom-Json
    $hit = $list | Where-Object { $_.name -eq $TunnelName } | Select-Object -First 1
    if ($hit) { $tunnelId = $hit.id }
}
if (-not $tunnelId) {
    $createOut = & $cf tunnel create $TunnelName 2>&1 | Out-String
    Write-Host $createOut
    if ($createOut -match "([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})") {
        $tunnelId = $Matches[1]
    }
    if (-not $tunnelId) {
        $listJson = & $cf tunnel list -o json
        $list = $listJson | ConvertFrom-Json
        $hit = $list | Where-Object { $_.name -eq $TunnelName } | Select-Object -First 1
        $tunnelId = $hit.id
    }
}
if (-not $tunnelId) { throw "Could not resolve tunnel id for $TunnelName" }
Write-Host "  Tunnel ID: $tunnelId"

$userCred = Join-Path $env:USERPROFILE ".cloudflared\$tunnelId.json"
if (-not (Test-Path $userCred)) {
    throw "Credentials not found: $userCred"
}
$credsDest = Join-Path $dataDir "credentials.json"
Copy-Item -Path $userCred -Destination $credsDest -Force

Write-Host "[3/5] DNS ルート: $Hostname" -ForegroundColor Yellow
& $cf tunnel route dns $TunnelName $Hostname
if ($LASTEXITCODE -ne 0) {
    Write-Host "  route dns failed — Cloudflare ダッシュボードで CNAME を手動設定:" -ForegroundColor Yellow
    Write-Host "  $Hostname -> $tunnelId.cfargotunnel.com"
}

$credsYaml = ($credsDest -replace "\\", "/")
$configPath = Join-Path $dataDir "config.yml"
@"
tunnel: $tunnelId
credentials-file: $credsYaml
protocol: quic
ingress:
  - hostname: $Hostname
    service: http://127.0.0.1:3000
  - service: http_status:404
"@ | Set-Content -Path $configPath -Encoding UTF8

$baseUrl = "https://$Hostname"
$metaPath = Join-Path $Root "data\fixed-url.json"
@{
    base_url    = $baseUrl
    hostname    = $Hostname
    tunnel_name = $TunnelName
    tunnel_id   = $tunnelId
    configured_at = (Get-Date).ToString("o")
} | ConvertTo-Json | Set-Content -Path $metaPath -Encoding UTF8

Write-Host "[4/5] .env 更新 (CORS / PUBLIC_HOSTNAME)" -ForegroundColor Yellow
$envPath = Join-Path $Root ".env"
$lines = @()
if (Test-Path $envPath) { $lines = @(Get-Content $envPath -Encoding UTF8) }
$newLines = [System.Collections.Generic.List[string]]::new()
$keys = @("PUBLIC_HOSTNAME", "PUBLIC_ACCESS", "HELIX_COOKIE_SECURE", "API_URL_INTERNAL", "CORS_ORIGINS")
$lan = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -notmatch "^127\." -and $_.InterfaceAlias -notmatch "vEthernet|WSL|Loopback" } |
    Select-Object -First 1 -ExpandProperty IPAddress)
$cors = "https://$Hostname,http://127.0.0.1:3000,http://localhost:3000"
if ($lan) { $cors += ",http://${lan}:3000" }
$set = @{
    PUBLIC_HOSTNAME    = $Hostname
    PUBLIC_ACCESS      = "1"
    HELIX_COOKIE_SECURE = "1"
    API_URL_INTERNAL   = "http://127.0.0.1:8000"
    CORS_ORIGINS       = $cors
}
foreach ($line in $lines) {
    $skip = $false
    foreach ($k in $keys) {
        if ($line -match "^$([regex]::Escape($k))=") { $skip = $true; break }
    }
    if (-not $skip) { [void]$newLines.Add($line) }
}
foreach ($k in $keys) { [void]$newLines.Add("$k=$($set[$k])") }
$newLines | Set-Content -Path $envPath -Encoding UTF8

Write-Host "[5/5] 固定URLファイル更新" -ForegroundColor Yellow
Update-PublicUrlFileFixed -Root $Root -PublicBaseUrl $baseUrl -LanIp $lan

Write-Host ""
Write-Host "完了 — 固定URL:" -ForegroundColor Green
Write-Host "  $baseUrl/welcome"
Write-Host ""
Write-Host "次: API/UI を起動してから固定トンネルを開始:" -ForegroundColor Cyan
Write-Host "  .\scripts\quick-restart-public.ps1"
Write-Host ""
Write-Host "ログオン自動起動を再登録する場合:" -ForegroundColor Cyan
Write-Host "  .\scripts\install-autostart.ps1"
