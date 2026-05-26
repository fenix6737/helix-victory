# GitHub Actions 自動化 — リポジトリ作成・push・Secrets 登録（PC不要収集＋深夜サイクル）
# 使い方:
#   .\scripts\setup-github-automation.ps1
#   .\scripts\setup-github-automation.ps1 -RepoName "helix-victory" -Visibility private
param(
    [string]$RepoName = "helix-victory",
    [ValidateSet("private", "public")]
    [string]$Visibility = "private",
    [switch]$SkipPush,
    [switch]$SkipSecrets
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $MyInvocation.MyCommand.Path) -Parent
Set-Location $Root

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Get-GhExe {
    $gh = Get-Command gh -ErrorAction SilentlyContinue
    if ($gh) { return $gh.Source }
    $candidates = @(
        "${env:ProgramFiles}\GitHub CLI\gh.exe",
        "${env:ProgramFiles(x86)}\GitHub CLI\gh.exe",
        "$env:LOCALAPPDATA\Programs\GitHub CLI\gh.exe"
    )
    foreach ($p in $candidates) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

function Ensure-GhCli {
    $exe = Get-GhExe
    if ($exe) { return $exe }
    Write-Step "Installing GitHub CLI (winget)"
    winget install --id GitHub.cli -e --accept-source-agreements --accept-package-agreements | Out-Null
    $exe = Get-GhExe
    if (-not $exe) {
        throw "gh not found. Install from https://cli.github.com/ and re-run."
    }
    return $exe
}

function Load-FlyCredentials {
    $envFile = Join-Path $Root "deploy\fly-deployed.local.env"
    if (-not (Test-Path $envFile)) {
        throw "Missing $envFile — run .\scripts\deploy-fly-simple.ps1 first."
    }
    $vars = @{}
    Get-Content $envFile -Encoding UTF8 | ForEach-Object {
        if ($_ -match '^([^#=]+)=(.*)$') {
            $vars[$matches[1].Trim()] = $matches[2].Trim()
        }
    }
    if (-not $vars["HELIX_PUBLIC_URL"]) {
        $vars["HELIX_PUBLIC_URL"] = "https://helix-victory.fly.dev"
    }
    foreach ($req in @("ADMIN_USERNAME", "ADMIN_PASSWORD", "INGEST_API_KEY")) {
        if (-not $vars[$req]) {
            throw "Missing $req in fly-deployed.local.env"
        }
    }
    return $vars
}

function Ensure-GitRepo {
    if (-not (Test-Path (Join-Path $Root ".git"))) {
        Write-Step "git init"
        git init $Root | Out-Null
    }
    git -C $Root config core.autocrlf true 2>$null | Out-Null
}

function Test-GhLoggedIn {
    param([string]$GhExe)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    & $GhExe auth status 1>$null 2>$null | Out-Null
    $ok = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $prev
    return $ok
}

function Ensure-GhAuth {
    param([string]$GhExe)
    if (Test-GhLoggedIn -GhExe $GhExe) {
        Write-Host "GitHub: login OK" -ForegroundColor Green
        return
    }
    Write-Host ""
    Write-Host "=== GitHub login (first time) ===" -ForegroundColor Yellow
    Write-Host "Browser opens -> sign in -> Authorize -> return to this window." -ForegroundColor Yellow
    Write-Host ""
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $GhExe auth login -h github.com -p https -w
    $loginCode = $LASTEXITCODE
    $ErrorActionPreference = $prev
    if ($loginCode -ne 0) {
        throw "GitHub login cancelled or failed. Run manually: gh auth login"
    }
    if (-not (Test-GhLoggedIn -GhExe $GhExe)) {
        throw "Login finished but gh is not authenticated. Run: gh auth login"
    }
    Write-Host "GitHub: login OK" -ForegroundColor Green
}

function Set-GhSecrets {
    param([string]$GhExe, [hashtable]$Vars)
    Write-Step "Registering GitHub Actions secrets"
    $map = @{
        HELIX_API_URL  = $Vars["HELIX_PUBLIC_URL"]
        INGEST_API_KEY = $Vars["INGEST_API_KEY"]
        ADMIN_USERNAME = $Vars["ADMIN_USERNAME"]
        ADMIN_PASSWORD = $Vars["ADMIN_PASSWORD"]
    }
    foreach ($pair in $map.GetEnumerator()) {
        & $GhExe secret set $pair.Key --body $pair.Value | Out-Null
        Write-Host "  secret: $($pair.Key)" -ForegroundColor Green
    }

    $authJson = Join-Path $Root "collector\daidata_auth.json"
    if (Test-Path $authJson) {
        $b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($authJson))
        & $GhExe secret set DAIDATA_AUTH_B64 --body $b64 | Out-Null
        Write-Host "  secret: DAIDATA_AUTH_B64 (from collector\daidata_auth.json)" -ForegroundColor Green
    } else {
        Write-Host "  skip: DAIDATA_AUTH_B64 (no daidata_auth.json — maruhan scrape may fail)" -ForegroundColor Yellow
    }
}

function Remove-BadGitRemote {
    $url = git -C $Root remote get-url origin 2>$null
    if ($url -and $url -match "fly\.dev") {
        Write-Host "Removing wrong origin (fly.dev is not a git server): $url" -ForegroundColor Yellow
        git -C $Root remote remove origin 2>$null | Out-Null
    }
}

function Push-GitHubRepo {
    param([string]$GhExe, [string]$Name, [string]$Vis)
    Write-Step "Git commit (if needed)"
    Ensure-GitRepo
    Remove-BadGitRemote
    git -C $Root add -A 2>$null
    $pending = git -C $Root status --porcelain 2>$null
    if ($pending) {
        git -C $Root commit -m "Helix Victory: Fly deploy, GitHub Actions automation, developer spec tests" | Out-Null
    }

    $remote = git -C $Root remote get-url origin 2>$null
    if (-not $remote) {
        Write-Step "Create GitHub repo and push"
        $visFlag = if ($Vis -eq "public") { "--public" } else { "--private" }
        & $GhExe repo create $Name --source $Root --remote origin $visFlag --push
    } elseif (-not $SkipPush) {
        Write-Step "git push origin"
        git -C $Root push -u origin HEAD
    }
}

Write-Host "Helix Victory - GitHub automation setup" -ForegroundColor Cyan
Write-Host ""
Write-Host "NOTE: Do NOT use https://helix-victory.fly.dev as a Git URL." -ForegroundColor Yellow
Write-Host "      fly.dev = website only. Git lives on github.com/username/$RepoName" -ForegroundColor Yellow
Write-Host ""

$ghExe = Ensure-GhCli
$vars = Load-FlyCredentials
Ensure-GhAuth -GhExe $ghExe

if (-not $SkipPush) {
    Push-GitHubRepo -GhExe $ghExe -Name $RepoName -Vis $Visibility
}

if (-not $SkipSecrets) {
    Set-GhSecrets -GhExe $ghExe -Vars $vars
}

Write-Step "Enable workflows (manual run)"
$prev = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
$owner = (& $ghExe api user -q .login 2>$null)
$ErrorActionPreference = $prev
$owner = if ($owner) { $owner.ToString().Trim() } else { "" }
if ($owner) {
    Write-Host "  Cloud Collect:" -ForegroundColor White
    Write-Host "    https://github.com/$owner/$RepoName/actions/workflows/cloud-collect.yml"
    Write-Host "  Midnight JST cycle:" -ForegroundColor White
    Write-Host "    https://github.com/$owner/$RepoName/actions/workflows/midnight-jst-daily-cycle.yml"
    Write-Host ""
    Write-Host "  Run workflow -> Run workflow (test now)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host "  Collect: every 3 hours (UTC cron)" -ForegroundColor Gray
Write-Host "  Daily learning: 00:10 JST" -ForegroundColor Gray
Write-Host "  No PC required after this." -ForegroundColor Gray
