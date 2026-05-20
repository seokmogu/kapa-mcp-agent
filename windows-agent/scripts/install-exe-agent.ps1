param(
  [string]$ExePath = ".\kapa-agent.exe",
  [string]$InstallDir = "C:\KapaAgent",
  [string]$BindHost = "127.0.0.1",
  [int]$Port = 8765,
  [string]$ControllerIp = "",
  [string]$Token = ""
)

$ErrorActionPreference = "Stop"

$ResolvedExe = Resolve-Path $ExePath
$InstallPath = New-Item -ItemType Directory -Force -Path $InstallDir

Copy-Item -Path $ResolvedExe -Destination (Join-Path $InstallPath "kapa-agent.exe") -Force
Copy-Item -Path (Join-Path $PSScriptRoot "run-agent-exe.ps1") -Destination $InstallPath -Force
Copy-Item -Path (Join-Path $PSScriptRoot "smoke-test.ps1") -Destination $InstallPath -Force

$Config = @{
  bind_host = $BindHost
  port = $Port
  artifact_dir = "artifacts"
  log_dir = "logs"
  auth_token = $(if ($Token.Length -gt 0) { $Token } else { $null })
  default_window_patterns = @{
    kapa_hub_plus = ".*(KAPA\s*HUB|KAPA-HUB).*"
    kais = ".*(부동산통합업무시스템|KAIS).*"
  }
  recipes = @{
    "kapa_hub_plus.search_address" = @()
    "kais.search_address" = @()
  }
}

$Config | ConvertTo-Json -Depth 10 | Set-Content -Path (Join-Path $InstallPath "config.local.json") -Encoding UTF8

$TaskName = "KapaAgent"
$TaskCommand = "powershell.exe"
$TaskArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$InstallDir\run-agent-exe.ps1`" -InstallDir `"$InstallDir`""

schtasks /Create /TN $TaskName /TR "$TaskCommand $TaskArgs" /SC ONLOGON /RL HIGHEST /F | Out-Host

if ($ControllerIp.Length -gt 0) {
  $RuleName = "Kapa Agent via Tailscale"
  $Existing = Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue
  if ($Existing) {
    Remove-NetFirewallRule -DisplayName $RuleName
  }
  New-NetFirewallRule `
    -DisplayName $RuleName `
    -Direction Inbound `
    -Action Allow `
    -Protocol TCP `
    -LocalPort $Port `
    -RemoteAddress $ControllerIp | Out-Host
}

Write-Host "Installed EXE agent. Start now with:"
Write-Host "  schtasks /Run /TN $TaskName"
Write-Host "Or run directly:"
Write-Host "  $InstallDir\kapa-agent.exe"

