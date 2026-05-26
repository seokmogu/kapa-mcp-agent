param(
  [string]$Python = ".\.venv\Scripts\python.exe",
  [string]$OutDir = "",
  [string]$WindowPattern = "(KAPA|HUB|KAIS)",
  [switch]$IncludeClipboardText,
  [switch]$IncludeScreenshotFiles,
  [string]$PushUrl = "",
  [string]$PushToken = ""
)

$ErrorActionPreference = "Stop"

$SourceRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $SourceRoot

if (-not (Test-Path $Python)) {
  $Python = "python"
}

$ArgsList = @(
  "-m", "kapa_agent.capability_probe",
  "--window-pattern", $WindowPattern
)

if ($OutDir) {
  $ArgsList += @("--out-dir", $OutDir)
}
if ($IncludeClipboardText) {
  $ArgsList += "--include-clipboard-text"
}
if ($IncludeScreenshotFiles) {
  $ArgsList += "--include-screenshot-files"
}
if ($PushUrl) {
  $ArgsList += @("--push-url", $PushUrl)
}
if ($PushToken) {
  $ArgsList += @("--push-token", $PushToken)
}

& $Python @ArgsList
