# gh ログイン後に実行 — リポジトリ作成・push・Cloud Collect 手動起動
$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $MyInvocation.MyCommand.Path) -Parent
Set-Location $Root

$gh = "${env:ProgramFiles}\GitHub CLI\gh.exe"
if (-not (Test-Path $gh)) { throw "Install GitHub CLI first." }

$prev = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
& $gh auth status 1>$null 2>$null
$authed = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = $prev

if (-not $authed) {
    Write-Host "GitHub not logged in. Run:" -ForegroundColor Yellow
    Write-Host "  gh auth login" -ForegroundColor White
    Write-Host "Then run this script again." -ForegroundColor Yellow
    exit 1
}

$user = (& $gh api user -q .login).Trim()
$repo = "helix-victory"
Write-Host "GitHub user: $user" -ForegroundColor Green

$origin = "https://github.com/$user/$repo.git"
$prevEa = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
$hasOrigin = git remote get-url origin 2>$null
if ($LASTEXITCODE -eq 0) {
    git remote remove origin 2>$null | Out-Null
}
$ErrorActionPreference = $prevEa
$exists = $false
$prev = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
& $gh repo view "$user/$repo" 1>$null 2>$null
$exists = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = $prev

if (-not $exists) {
    Write-Host "Creating repo $user/$repo ..." -ForegroundColor Cyan
    & $gh repo create $repo --private --source . --remote origin --push
} else {
    $prevEa = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    git remote get-url origin 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { git remote add origin $origin }
    else { git remote set-url origin $origin }
    $ErrorActionPreference = $prevEa
    git add -A
    if (git status --porcelain) { git commit -m "Update Helix Victory automation" }
    git branch -M main 2>$null
    git push -u origin main
    if ($LASTEXITCODE -ne 0) { throw "git push failed (exit $LASTEXITCODE)" }
}

Write-Host "Registering Actions secrets ..." -ForegroundColor Cyan
$envFile = Join-Path $Root "deploy\fly-deployed.local.env"
if (Test-Path $envFile) {
    $vars = @{}
    Get-Content $envFile -Encoding UTF8 | ForEach-Object {
        if ($_ -match '^([^#=]+)=(.*)$') { $vars[$matches[1].Trim()] = $matches[2].Trim() }
    }
    if ($vars["HELIX_PUBLIC_URL"]) {
        & $gh secret set HELIX_API_URL --body $vars["HELIX_PUBLIC_URL"] --repo "$user/$repo" | Out-Null
        & $gh secret set INGEST_API_KEY --body $vars["INGEST_API_KEY"] --repo "$user/$repo" | Out-Null
        & $gh secret set ADMIN_USERNAME --body $vars["ADMIN_USERNAME"] --repo "$user/$repo" | Out-Null
        & $gh secret set ADMIN_PASSWORD --body $vars["ADMIN_PASSWORD"] --repo "$user/$repo" | Out-Null
        Write-Host "  secrets updated on $user/$repo" -ForegroundColor Green
    }
}

Write-Host "Triggering Cloud Collect ..." -ForegroundColor Cyan
& $gh workflow run "cloud-collect.yml" --repo "$user/$repo"
Write-Host ""
Write-Host "Done:" -ForegroundColor Green
Write-Host "  https://github.com/$user/$repo/actions" -ForegroundColor White
