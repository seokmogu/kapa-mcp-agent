param(
  [string]$Python = "py -3.11",
  [Parameter(Mandatory = $true)]
  [string]$ProbePushUrl,
  [Parameter(Mandatory = $true)]
  [string]$ProbePushToken,
  [ValidateSet("raw-zip", "json-base64")]
  [string]$ProbePushFormat = "raw-zip",
  [string]$ProbeWindowPattern = "(KAPA|HUB|KAIS)",
  [string]$OutputName = "kapa-probe",
  [string]$OutputDir = "C:\KapaProbeBuild\dist",
  [switch]$IncludeClipboardText,
  [switch]$IncludeScreenshotFiles
)

$ErrorActionPreference = "Stop"

$SourceRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $SourceRoot
$ResolvedOutputDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputDir)
New-Item -ItemType Directory -Force -Path $ResolvedOutputDir | Out-Null

function Invoke-Checked {
  param(
    [scriptblock]$Script,
    [string]$Name
  )
  & $Script
  if ($LASTEXITCODE -ne 0) {
    throw "$Name failed with exit code $LASTEXITCODE"
  }
}

$BuildVenv = Join-Path $SourceRoot ".build-venv"
if (-not (Test-Path (Join-Path $BuildVenv "Scripts\python.exe"))) {
  Invoke-Expression "$Python -m venv `"$BuildVenv`""
}

$BuildPython = Join-Path $BuildVenv "Scripts\python.exe"
Invoke-Checked -Name "pip upgrade" -Script { & $BuildPython -m pip install --upgrade pip wheel setuptools }
Invoke-Checked -Name "pyinstaller install" -Script { & $BuildPython -m pip install pyinstaller }
Invoke-Checked -Name "package install" -Script { & $BuildPython -m pip install ".[probe]" }

$ProbeConfigDir = Join-Path $SourceRoot ".build-probe-config"
New-Item -ItemType Directory -Force -Path $ProbeConfigDir | Out-Null
$ProbeConfigPath = Join-Path $ProbeConfigDir "probe.config.json"
$ProbeConfig = [ordered]@{
  window_pattern = $ProbeWindowPattern
  max_depth = 6
  max_nodes = 1000
  recent_minutes = 240
  include_clipboard_text = [bool]$IncludeClipboardText
  include_screenshot_files = [bool]$IncludeScreenshotFiles
  push_url = $ProbePushUrl
  push_token = $ProbePushToken
  push_format = $ProbePushFormat
  terms = @(
    "KAPA",
    "HUB",
    "KAIS",
    "Excel",
    "XLS",
    "CSV",
    "PDF",
    "print",
    "export",
    "save",
    "copy",
    "search",
    "address"
  )
}
$ProbeConfig | ConvertTo-Json -Depth 5 | Set-Content -Path $ProbeConfigPath -Encoding UTF8

$CollectArgs = @(
  "--collect-submodules", "pywinauto",
  "--collect-submodules", "comtypes",
  "--collect-submodules", "mss",
  "--collect-submodules", "PIL",
  "--collect-submodules", "psutil",
  "--collect-submodules", "pyperclip",
  "--hidden-import", "win32timezone",
  "--hidden-import", "win32gui",
  "--hidden-import", "win32ui",
  "--hidden-import", "win32con",
  "--add-data", "$ProbeConfigPath;."
)

$BuildRoot = Join-Path $env:TEMP "kapa-probe-pyinstaller"
$WorkPath = Join-Path $BuildRoot "build"
$SpecPath = Join-Path $BuildRoot "spec"
New-Item -ItemType Directory -Force -Path $WorkPath | Out-Null
New-Item -ItemType Directory -Force -Path $SpecPath | Out-Null

Invoke-Checked -Name "pyinstaller build" -Script {
  & $BuildPython -m PyInstaller `
    --clean `
    --noconfirm `
    --onefile `
    --name $OutputName `
    --distpath $ResolvedOutputDir `
    --workpath $WorkPath `
    --specpath $SpecPath `
    @CollectArgs `
    (Join-Path $SourceRoot "run_probe.py")
}

$DistDir = $ResolvedOutputDir
$ExePath = Join-Path $DistDir "$OutputName.exe"

Write-Host "Built single-file probe EXE:"
Write-Host "  $ExePath"
