# Fly デプロイ後 — GitHub Actions secrets を fly-deployed.local.env と同期
param(
    [string]$Root = "",
    [string]$Repo = "fenix6737/helix-victory"
)

$ErrorActionPreference = "Stop"
if (-not $Root) {
    $Root = Split-Path (Split-Path $MyInvocation.MyCommand.Path) -Parent
}

$gh = Get-Command gh -ErrorAction SilentlyContinue
if (-not $gh) {
    Write-Host "gh CLI not found — skip GitHub secret sync" -ForegroundColor Yellow
    exit 0
}

$envFile = Join-Path $Root "deploy\fly-deployed.local.env"
if (-not (Test-Path $envFile)) {
    Write-Host "Missing $envFile — skip GitHub secret sync" -ForegroundColor Yellow
    exit 0
}

$vars = @{}
Get-Content $envFile -Encoding UTF8 | ForEach-Object {
    if ($_ -match '^([^#=]+)=(.*)$') { $vars[$matches[1].Trim()] = $matches[2].Trim() }
}

$required = @("HELIX_PUBLIC_URL", "INGEST_API_KEY", "ADMIN_USERNAME", "ADMIN_PASSWORD")
foreach ($k in $required) {
    if (-not $vars[$k]) {
        Write-Host "Missing $k in fly-deployed.local.env" -ForegroundColor Red
        exit 1
    }
}

& gh secret set HELIX_API_URL --body $vars["HELIX_PUBLIC_URL"] --repo $Repo | Out-Null
& gh secret set INGEST_API_KEY --body $vars["INGEST_API_KEY"] --repo $Repo | Out-Null
& gh secret set ADMIN_USERNAME --body $vars["ADMIN_USERNAME"] --repo $Repo | Out-Null
& gh secret set ADMIN_PASSWORD --body $vars["ADMIN_PASSWORD"] --repo $Repo | Out-Null
Write-Host "GitHub secrets synced for $Repo" -ForegroundColor Green
