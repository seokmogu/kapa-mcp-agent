param(
  [string]$ExePath = ".\kapa-probe.exe",
  [string]$ConfigPath = ".\probe.config.json"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $ExePath)) {
  if (Test-Path ".\kapa-probe\kapa-probe.exe") {
    $ExePath = ".\kapa-probe\kapa-probe.exe"
  } else {
    throw "Cannot find kapa-probe.exe"
  }
}

if (Test-Path $ConfigPath) {
  & $ExePath --config $ConfigPath
} else {
  & $ExePath
}
