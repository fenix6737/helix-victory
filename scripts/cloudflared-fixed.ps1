# 固定URL用 Cloudflare 名前付きトンネル — 共通関数
param()

function Get-HelixRoot {
    param([string]$FromScript)
    Split-Path -Parent $FromScript | Split-Path -Parent
}

function Get-FixedTunnelPaths {
    param([string]$Root)
    @{
        Config    = Join-Path $Root "data\cloudflared\config.yml"
        Creds     = Join-Path $Root "data\cloudflared\credentials.json"
        Meta      = Join-Path $Root "data\fixed-url.json"
        TunnelLog = Join-Path $Root "data\cloudflared-run.log"
    }
}

function Test-FixedTunnelConfigured {
    param([string]$Root)
    $p = Get-FixedTunnelPaths $Root
    return (Test-Path $p.Config) -and (Test-Path $p.Creds) -and (Test-Path $p.Meta)
}

function Get-FixedPublicBaseUrl {
    param([string]$Root)
    $p = Get-FixedTunnelPaths $Root
    if (-not (Test-Path $p.Meta)) { return $null }
    try {
        $j = Get-Content $p.Meta -Raw -Encoding UTF8 | ConvertFrom-Json
        $u = [string]$j.base_url
        if ($u) { return $u.TrimEnd("/") }
    } catch { }
    return $null
}

function Get-CloudflaredExePath {
    param([string]$Root)
    $cfBin = Join-Path $Root "scripts\bin\cloudflared.exe"
    if (Get-Command cloudflared -ErrorAction SilentlyContinue) { return "cloudflared" }
    if (Test-Path $cfBin) { return $cfBin }
    return $null
}

function Start-FixedCloudflaredTunnel {
    param(
        [string]$Root,
        [scriptblock]$Log = { param($m) Write-Host $m }
    )
    if (-not (Test-FixedTunnelConfigured $Root)) {
        & $Log "Fixed tunnel not configured"
        return $null
    }
    $p = Get-FixedTunnelPaths $Root
    $base = Get-FixedPublicBaseUrl $Root
    if (-not $base) {
        & $Log "fixed-url.json missing base_url"
        return $null
    }
    $cf = Get-CloudflaredExePath $Root
    if (-not $cf) {
        & $Log "cloudflared not found"
        return $null
    }
    Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    if (Test-Path $p.TunnelLog) { Remove-Item $p.TunnelLog -Force -ErrorAction SilentlyContinue }
    & $Log "Starting fixed Cloudflare tunnel -> $base"
    Start-Process -WindowStyle Hidden -FilePath $cf `
        -ArgumentList @("tunnel", "--config", $p.Config, "run", "--no-autoupdate") `
        -RedirectStandardOutput $p.TunnelLog -RedirectStandardError ($p.TunnelLog + ".err")
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 2
        $code = & curl.exe -s -o NUL -w "%{http_code}" --max-time 8 "$base/welcome" 2>$null
        if ($code -eq "200") {
            & $Log "Fixed tunnel healthy: $base"
            return $base
        }
    }
    & $Log "Fixed tunnel started but /welcome not 200 yet — URL is still $base"
    return $base
}

function Get-EnvPublicBaseUrl {
    param([string]$Root)
    $envPath = Join-Path $Root ".env"
    if (-not (Test-Path $envPath)) { return $null }
    foreach ($line in Get-Content $envPath -Encoding UTF8) {
        if ($line -match '^(?:HELIX_PUBLIC_URL|PUBLIC_BASE_URL|FLY_APP_URL)=(.+)$') {
            $u = $Matches[1].Trim().TrimEnd("/")
            if ($u) { return $u }
        }
    }
    return $null
}

function Start-QuickCloudflaredTunnel {
    param(
        [string]$Root,
        [string]$TunnelLog,
        [scriptblock]$Log = { param($m) Write-Host $m }
    )
    $cf = Get-CloudflaredExePath $Root
    if (-not $cf) { return $null }
    . (Join-Path $Root "scripts\public-url-helper.ps1")
    $errLog = "$TunnelLog.err"
    if (Test-Path $TunnelLog) { Remove-Item $TunnelLog -Force -ErrorAction SilentlyContinue }
    if (Test-Path $errLog) { Remove-Item $errLog -Force -ErrorAction SilentlyContinue }
    Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    & $Log "Starting quick tunnel (free, URL changes on reboot)"
    Start-Process -WindowStyle Hidden -FilePath $cf `
        -ArgumentList @("tunnel", "--url", "http://127.0.0.1:3000", "--no-autoupdate") `
        -RedirectStandardOutput $TunnelLog -RedirectStandardError $errLog
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 2
        $parts = @()
        if (Test-Path $TunnelLog) { $parts += Get-Content $TunnelLog -Raw -EA SilentlyContinue }
        if (Test-Path $errLog) { $parts += Get-Content $errLog -Raw -EA SilentlyContinue }
        if (($parts -join "`n") -match "(https://[a-z0-9-]+\.trycloudflare\.com)") {
            $url = $Matches[1]
            if (Test-PublicBaseUrlReachable $url) { return $url }
        }
    }
    return $null
}

function Update-PublicUrlFileFixed {
    param(
        [string]$Root,
        [string]$PublicBaseUrl,
        [string]$LanIp = $null
    )
    $urlFile = Join-Path $Root "data\public-url.txt"
    $lines = @()
    $lines += "Helix Victory — public access (FIXED URL)"
    $lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    $lines += ""
    $lines += "Local:"
    $lines += "  http://127.0.0.1:3000/welcome"
    $lines += ""
    if ($LanIp) {
        $lines += "LAN (same Wi-Fi):"
        $lines += "  http://${LanIp}:3000/welcome"
        $lines += ""
    }
    if ($PublicBaseUrl) {
        $t = $PublicBaseUrl.TrimEnd("/")
        $lines += "Internet (HTTPS) — 固定URL（再起動しても同じ）:"
        $lines += "  $t/welcome"
        $lines += "  $t/login"
        $lines += ""
    }
    $lines += "Config: data/fixed-url.json"
    $lines += "Log: data/autostart.log"
    Set-Content -Path $urlFile -Value ($lines -join "`n") -Encoding UTF8
}

function Update-PublicUrlFileFree {
    param(
        [string]$Root,
        [string]$PublicBaseUrl,
        [string]$LanIp = $null,
        [string]$Mode = "quick"
    )
    $urlFile = Join-Path $Root "data\public-url.txt"
    $lines = @()
    $lines += "Helix Victory — public access (完全無料運営)"
    $lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    $lines += ""
    if ($Mode -eq "cloud") {
        $lines += "Internet (HTTPS) — 固定・無料（Fly/Oracle 常時稼働）:"
    } elseif ($Mode -eq "fixed") {
        $lines += "Internet (HTTPS) — 固定（Cloudflare名前付き・ドメイン要）:"
    } else {
        $lines += "Internet (HTTPS) — 無料・一時URL（PC再起動で変わる）:"
    }
    $t = $PublicBaseUrl.TrimEnd("/")
    $lines += "  $t/welcome"
    $lines += "  $t/login"
    $lines += ""
    $lines += "Local: http://127.0.0.1:3000/welcome"
    if ($LanIp) { $lines += "LAN: http://${LanIp}:3000/welcome" }
    $lines += ""
    $lines += "固定無料URL: docs/DEPLOY_FREE_24x7.md (Fly.io)"
    $lines += "Log: data/autostart.log"
    Set-Content -Path $urlFile -Value ($lines -join "`n") -Encoding UTF8
}
