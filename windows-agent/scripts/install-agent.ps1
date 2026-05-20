param(
  [string]$InstallDir = "C:\KapaAgent",
  [string]$BindHost = "127.0.0.1",
  [int]$Port = 8765,
  [string]$ControllerIp = "",
  [string]$Token = ""
)

$ErrorActionPreference = "Stop"

$SourceRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$InstallPath = New-Item -ItemType Directory -Force -Path $InstallDir

Write-Host "Installing KAPA Agent to $InstallPath"

Copy-Item -Path (Join-Path $SourceRoot "kapa_agent") -Destination $InstallPath -Recurse -Force
Copy-Item -Path (Join-Path $SourceRoot "pyproject.toml") -Destination $InstallPath -Force
Copy-Item -Path (Join-Path $SourceRoot "config.example.json") -Destination $InstallPath -Force
Copy-Item -Path (Join-Path $SourceRoot "scripts\run-agent.ps1") -Destination $InstallPath -Force
Copy-Item -Path (Join-Path $SourceRoot "scripts\smoke-test.ps1") -Destination $InstallPath -Force

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

if (-not (Test-Path (Join-Path $InstallPath ".venv\Scripts\python.exe"))) {
  py -3.11 -m venv (Join-Path $InstallPath ".venv")
}

$Python = Join-Path $InstallPath ".venv\Scripts\python.exe"
& $Python -m pip install --upgrade pip
& $Python -m pip install $InstallPath

$TaskName = "KapaAgent"
$TaskCommand = "powershell.exe"
$TaskArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$InstallDir\run-agent.ps1`" -InstallDir `"$InstallDir`""

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

Write-Host "Installed. Start now with:"
Write-Host "  schtasks /Run /TN $TaskName"
Write-Host "Health check:"
Write-Host "  Invoke-RestMethod http://$BindHost`:$Port/health"
