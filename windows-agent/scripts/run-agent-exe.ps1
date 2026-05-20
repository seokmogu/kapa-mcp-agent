param(
  [string]$InstallDir = "C:\KapaAgent",
  [string]$ExeName = "kapa-agent.exe"
)

$ErrorActionPreference = "Stop"

$ConfigPath = Join-Path $InstallDir "config.local.json"
$ExePath = Join-Path $InstallDir $ExeName

if (-not (Test-Path $ExePath)) {
  throw "Agent executable not found: $ExePath"
}

if (Test-Path $ConfigPath) {
  $env:KAPA_AGENT_CONFIG = $ConfigPath
}

Set-Location $InstallDir
& $ExePath

