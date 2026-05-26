# 蝗ｺ螳啅RL繧呈怙遏ｭ縺ｧ 窶・Fly.io 縺ｮ縺ｿ・・racle / Neon / 繝峨Γ繧､繝ｳ荳崎ｦ・ｼ・
# 蛻晏屓: winget install flyctl  縺ｾ縺溘・ https://fly.io/docs/hands-on/install-flyctl/
# 螳溯｡・ .\scripts\deploy-fly-simple.ps1
param(
    [string]$AppName = "helix-victory",
    [string]$Region = "nrt",
    [switch]$SkipDeploy
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $MyInvocation.MyCommand.Path) -Parent
Set-Location $Root

function Get-FlyctlExe {
    if ($env:FLYCTL_INSTALL -and (Test-Path (Join-Path $env:FLYCTL_INSTALL "flyctl.exe"))) {
        return (Join-Path $env:FLYCTL_INSTALL "flyctl.exe")
    }
    $cmd = Get-Command fly -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $cmd = Get-Command flyctl -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $winget = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages\Fly-io.flyctl_Microsoft.Winget.Source_8wekyb3d8bbwe\flyctl.exe"
    if (Test-Path $winget) { return $winget }
    return $null
}

function Invoke-Fly {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$FlyCliArgs)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $script:FlyExe @FlyCliArgs 2>&1 | ForEach-Object { if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.ToString() } else { $_ } }
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    if ($code -ne 0) { exit $code }
}

function Get-FlyOutput {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$FlyCliArgs)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $out = & $script:FlyExe @FlyCliArgs 2>&1
    $ErrorActionPreference = $prev
    return ($out | Out-String)
}

function New-Secret {
    return (-join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | ForEach-Object { [char]$_ }))
}

$script:FlyExe = Get-FlyctlExe
if (-not $script:FlyExe) {
    Write-Host "flyctl 縺後≠繧翫∪縺帙ｓ縲ゅう繝ｳ繧ｹ繝医・繝ｫ蠕後↓蜀榊ｮ溯｡・" -ForegroundColor Red
    Write-Host "  winget install flyctl"
    exit 1
}

$publicUrl = "https://${AppName}.fly.dev"
Write-Host "Helix Victory 窶・Fly 蝗ｺ螳啅RL繝・・繝ｭ繧､" -ForegroundColor Cyan
Write-Host "flyctl: $script:FlyExe"
Write-Host "蜈ｬ髢偽RL: $publicUrl/welcome"
Write-Host ""

$whoami = Get-FlyOutput auth whoami
if ($whoami -notmatch '@') {
    Write-Host "繝悶Λ繧ｦ繧ｶ縺ｧ Fly 縺ｫ繝ｭ繧ｰ繧､繝ｳ..." -ForegroundColor Yellow
    Invoke-Fly auth login
} else {
    Write-Host "Fly 繝ｭ繧ｰ繧､繝ｳ貂・ $($whoami.Split("`n")[0])" -ForegroundColor Green
}

$apps = Get-FlyOutput apps list
if ($apps -notmatch [regex]::Escape($AppName)) {
    Write-Host "Creating app: $AppName ($Region)" -ForegroundColor Cyan
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $script:FlyExe apps create $AppName --org personal 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        $ErrorActionPreference = $prev
        Invoke-Fly launch --no-deploy --copy-config --name $AppName --region $Region --yes
    } else {
        $ErrorActionPreference = $prev
    }
}

$volList = Get-FlyOutput volumes list -a $AppName
if ($volList -notmatch "helix_data") {
    Write-Host "繝・・繧ｿ逕ｨ繝懊Μ繝･繝ｼ繝菴懈・ (SQLite)..." -ForegroundColor Cyan
    Invoke-Fly volumes create helix_data -a $AppName -r $Region --size 1 -y
}

$adminPass = New-Secret
$jwt = (New-Secret) + (New-Secret)
$ingest = New-Secret

Write-Host "繧ｷ繝ｼ繧ｯ繝ｬ繝・ヨ險ｭ螳・.." -ForegroundColor Cyan
Invoke-Fly secrets set `
    DATABASE_URL="sqlite+aiosqlite:////data/helix.db" `
    ADMIN_USERNAME="helix_admin" `
    ADMIN_PASSWORD="$adminPass" `
    JWT_SECRET="$jwt" `
    INGEST_API_KEY="$ingest" `
    CORS_ORIGINS="$publicUrl" `
    PUBLIC_ACCESS="1" `
    -a $AppName

$credFile = Join-Path $Root "deploy\fly-deployed.local.env"
@(
    "# auto-generated - do not commit",
    "HELIX_PUBLIC_URL=$publicUrl",
    "ADMIN_USERNAME=helix_admin",
    "ADMIN_PASSWORD=$adminPass",
    "INGEST_API_KEY=$ingest",
    "JWT_SECRET=$jwt"
) | Set-Content -Path $credFile -Encoding UTF8

if (-not $SkipDeploy) {
    Write-Host "繝・・繝ｭ繧､荳ｭ・域焚蛻・ｼ・.." -ForegroundColor Cyan
    Invoke-Fly deploy -a $AppName
}

# 閾ｪ螳・C .env 縺ｫ蝗ｺ螳啅RL・医ヨ繝ｳ繝阪Ν荳崎ｦ・ｼ・
$envPath = Join-Path $Root ".env"
$helixLine = "HELIX_PUBLIC_URL=$publicUrl"
if (Test-Path $envPath) {
    $lines = Get-Content $envPath -Encoding UTF8
    $lines = $lines | Where-Object { $_ -notmatch '^HELIX_PUBLIC_URL=' }
    $lines += $helixLine
    Set-Content -Path $envPath -Value $lines -Encoding UTF8
} else {
    Set-Content -Path $envPath -Value $helixLine -Encoding UTF8
}

Write-Host ""
Write-Host "Done" -ForegroundColor Green
Write-Host "  URL: $publicUrl/welcome"
Write-Host "  Login: $publicUrl/login"
Write-Host "  Credentials: deploy\fly-deployed.local.env"
