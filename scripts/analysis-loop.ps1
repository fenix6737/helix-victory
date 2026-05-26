# 2時間ごとに periodic_analysis.py を実行（常駐・非対話）
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
Set-Location $Root
. (Join-Path $Root "scripts\helix-core.ps1")

$script = Join-Path $Root "scripts\periodic_analysis.py"
$py = if (Get-Command py -ErrorAction SilentlyContinue) { @{ File = "py"; Args = @("-3.12") } }
      elseif (Test-Path "C:\Python312\python.exe") { @{ File = "C:\Python312\python.exe"; Args = @() } }
      else { @{ File = "python"; Args = @() } }

while ($true) {
    Start-Sleep -Seconds 7200
    try {
        if ($py.Args.Count -gt 0) {
            & $py.File ($py.Args + $script) 2>&1 | Out-Null
        } else {
            & $py.File $script 2>&1 | Out-Null
        }
    } catch { }
}
