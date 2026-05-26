# Install Docker Desktop (if missing) and start postgres/redis
$dockerPaths = @(
    "$env:ProgramFiles\Docker\Docker\resources\bin\docker.exe",
    "${env:ProgramFiles(x86)}\Docker\Docker\resources\bin\docker.exe"
)
$docker = $dockerPaths | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $docker) {
    Write-Host "Docker Desktop not found. Installing via winget..."
    winget install -e --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements
    Write-Host "After install, start Docker Desktop and run this script again."
    exit 1
}

$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
& $docker compose up -d
& $docker compose ps
