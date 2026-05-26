# Public URL save and display (trycloudflare etc.)
param()

function Get-HelixDataDir {
    param([string]$Root)
    Join-Path $Root "data"
}

function Get-PublicUrlJsonPath {
    param([string]$Root)
    Join-Path (Get-HelixDataDir $Root) "public-url.json"
}

function Test-PublicBaseUrlReachable {
    param(
        [string]$BaseUrl,
        [int]$TimeoutSec = 8
    )
    if (-not $BaseUrl) { return $false }
    $u = $BaseUrl.TrimEnd("/") + "/welcome"
    try {
        $code = & curl.exe -s -o NUL -w "%{http_code}" --max-time $TimeoutSec $u 2>$null
        return $code -eq "200"
    } catch {
        return $false
    }
}

function Save-PublicUrlManifest {
    param(
        [string]$Root,
        [string]$PublicBaseUrl,
        [string]$LanIp = $null,
        [string]$Mode = "quick",
        [string]$Source = "autostart"
    )
    $dataDir = Get-HelixDataDir $Root
    $null = New-Item -ItemType Directory -Force -Path $dataDir
    $base = $PublicBaseUrl.TrimEnd("/")
    $note = $null
    if ($Mode -eq "quick") {
        $note = "URL changes after each PC reboot. See data/public-url.txt for the latest."
    }
    $manifest = [ordered]@{
        updated_at  = (Get-Date).ToUniversalTime().ToString("o")
        mode        = $Mode
        source      = $Source
        public_url  = $base
        welcome_url = "$base/welcome"
        login_url   = "$base/login"
        local_url   = "http://127.0.0.1:3000/welcome"
        lan_url     = $(if ($LanIp) { "http://${LanIp}:3000/welcome" } else { $null })
        note        = $note
    }
    $jsonPath = Get-PublicUrlJsonPath $Root
    $json = $manifest | ConvertTo-Json -Depth 4
    [System.IO.File]::WriteAllText($jsonPath, $json, [System.Text.UTF8Encoding]::new($false))
    Update-DesktopPublicShortcut -Root $Root -WelcomeUrl $manifest.welcome_url
    return $manifest
}

function Update-DesktopPublicShortcut {
    param(
        [string]$Root,
        [string]$WelcomeUrl
    )
    if (-not $WelcomeUrl) { return }
    $desktop = [Environment]::GetFolderPath('Desktop')
    $urlPath = Join-Path $desktop 'Helix Victory (public).url'
    $lines = @(
        '[InternetShortcut]'
        "URL=$WelcomeUrl"
        'IconIndex=0'
    )
    Set-Content -Path $urlPath -Value $lines -Encoding ASCII
    $readme = Join-Path $desktop 'Helix Victory URL.txt'
    $readmeLines = @(
        'Helix Victory - current public URL'
        "Updated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
        ''
        'Bookmark on your phone:'
        $WelcomeUrl
        ''
        "Details: $Root\data\public-url.txt"
    )
    Set-Content -Path $readme -Value $readmeLines -Encoding UTF8
}

function Show-PublicUrlToUser {
    param(
        [string]$Root,
        [switch]$Quiet
    )
    $jsonPath = Get-PublicUrlJsonPath $Root
    if (-not (Test-Path $jsonPath)) {
        if (-not $Quiet) {
            Write-Host 'Public URL not ready yet. Check data/public-url.txt' -ForegroundColor Yellow
        }
        return $null
    }
    $m = Get-Content $jsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $welcome = [string]$m.welcome_url
    $urlFile = Join-Path $Root 'data\public-url.txt'

    if (-not $Quiet) {
        Write-Host ''
        Write-Host '=== Helix Victory public URL ===' -ForegroundColor Green
        Write-Host $welcome -ForegroundColor Cyan
        Write-Host "Saved: $urlFile"
        Write-Host ''
    }

    if (-not $Quiet) {
        try {
            Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
            $msg = "Bookmark on your phone:`n`n$welcome`n`n(URL changes after PC reboot)`n`nDetails: $urlFile"
            [void][System.Windows.Forms.MessageBox]::Show(
                $msg,
                'Helix Victory - Public URL',
                [System.Windows.Forms.MessageBoxButtons]::OK,
                [System.Windows.Forms.MessageBoxIcon]::Information
            )
        } catch {
            Write-Host "MessageBox skipped: $($_.Exception.Message)"
        }
        try { Start-Process $welcome } catch { }
        if (Test-Path $urlFile) {
            Start-Process notepad.exe $urlFile
        }
    }
    return $m
}

function Show-PublicUrlToast {
    param([string]$WelcomeUrl)
    if (-not $WelcomeUrl) { return }
    try {
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
        $escaped = [System.Security.SecurityElement]::Escape($WelcomeUrl)
        $template = "<toast><visual><binding template=`"ToastGeneric`"><text>Helix Victory</text><text>Public URL updated</text><text>$escaped</text></binding></visual></toast>"
        $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
        $xml.LoadXml($template)
        $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Helix.Victory').Show($toast)
    } catch {
        # ignore unsupported hosts
    }
}
