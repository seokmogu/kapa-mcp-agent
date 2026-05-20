param(
  [string]$InstallDir = "C:\KapaAgent",
  [switch]$RemoveFiles
)

$ErrorActionPreference = "Stop"

$TaskName = "KapaAgent"
schtasks /Delete /TN $TaskName /F 2>$null | Out-Null

$RuleName = "Kapa Agent via Tailscale"
$Existing = Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue
if ($Existing) {
  Remove-NetFirewallRule -DisplayName $RuleName
}

if ($RemoveFiles -and (Test-Path $InstallDir)) {
  Remove-Item -Recurse -Force $InstallDir
}

Write-Host "KAPA Agent uninstalled."

