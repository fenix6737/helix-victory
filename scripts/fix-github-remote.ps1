# 誤った origin（fly.dev / プレースホルダー）を直して push する
param(
    [string]$GitHubUser = "",
    [string]$RepoName = "helix-victory"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $MyInvocation.MyCommand.Path) -Parent
Set-Location $Root

$gh = "${env:ProgramFiles}\GitHub CLI\gh.exe"
if (-not $GitHubUser -and (Test-Path $gh)) {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    $GitHubUser = (& $gh api user -q .login 2>$null)
    $ErrorActionPreference = $prev
}
if (-not $GitHubUser) {
    $GitHubUser = Read-Host "GitHub username (e.g. eita00eizo)"
}

$url = "https://github.com/$GitHubUser/$RepoName.git"
Write-Host "origin -> $url" -ForegroundColor Cyan

git remote remove origin 2>$null | Out-Null
git remote add origin $url

git add -A
$pending = git status --porcelain
if ($pending) {
    git commit -m "Helix Victory: automation, developer spec, Fly fixes"
}

git push -u origin main
if ($LASTEXITCODE -ne 0) {
    git push -u origin master
}

Write-Host "Done. Actions: https://github.com/$GitHubUser/$RepoName/actions" -ForegroundColor Green
