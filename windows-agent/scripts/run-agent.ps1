param(
  [string]$InstallDir = "C:\KapaAgent"
)

$ErrorActionPreference = "Stop"

$ConfigPath = Join-Path $InstallDir "config.local.json"
$Python = Join-Path $InstallDir ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
  throw "Python virtual environment not found: $Python"
}

if (Test-Path $ConfigPath) {
  $env:KAPA_AGENT_CONFIG = $ConfigPath
}

Set-Location $InstallDir
& $Python -m kapa_agent.main

