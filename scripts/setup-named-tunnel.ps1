# 互換ラッパー — install-fixed-tunnel.ps1 を使用
param(
    [Parameter(Mandatory = $true)]
    [string]$Hostname,
    [string]$TunnelName = "helix-victory"
)
$install = Join-Path (Split-Path $MyInvocation.MyCommand.Path) "install-fixed-tunnel.ps1"
& $install -Hostname $Hostname -TunnelName $TunnelName
