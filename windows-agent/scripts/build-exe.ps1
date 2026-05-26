param(
  [string]$Python = "py -3.11",
  [string]$OutputName = "kapa-agent",
  [switch]$OneDir,
  [string]$ProbePushUrl = "",
  [string]$ProbePushToken = "",
  [ValidateSet("raw-zip", "json-base64")]
  [string]$ProbePushFormat = "raw-zip",
  [string]$ProbeWindowPattern = "(KAPA|HUB|KAIS)",
  [switch]$ProbeIncludeClipboardText,
  [switch]$ProbeIncludeScreenshotFiles
)

$ErrorActionPreference = "Stop"

$SourceRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $SourceRoot

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

$CollectArgs = @(
  "--collect-submodules", "pywinauto",
  "--collect-submodules", "comtypes",
  "--collect-submodules", "uvicorn",
  "--collect-submodules", "fastapi",
  "--collect-submodules", "pydantic",
  "--collect-submodules", "starlette",
  "--collect-submodules", "anyio",
  "--collect-submodules", "mss",
  "--collect-submodules", "PIL",
  "--collect-submodules", "psutil",
  "--collect-submodules", "pyperclip",
  "--hidden-import", "win32timezone",
  "--hidden-import", "win32gui",
  "--hidden-import", "win32ui",
  "--hidden-import", "win32con"
)

$ProbeConfigDir = Join-Path $SourceRoot ".build-probe-config"
New-Item -ItemType Directory -Force -Path $ProbeConfigDir | Out-Null
$ProbeConfigPath = Join-Path $ProbeConfigDir "probe.config.json"
$ProbeConfig = [ordered]@{
  window_pattern = $ProbeWindowPattern
  max_depth = 6
  max_nodes = 1000
  recent_minutes = 240
  include_clipboard_text = [bool]$ProbeIncludeClipboardText
  include_screenshot_files = [bool]$ProbeIncludeScreenshotFiles
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
$ProbeDataArgs = @("--add-data", "$ProbeConfigPath;.")

function Build-Executable {
  param(
    [string]$Name,
    [string]$EntryPoint,
    [string[]]$ExtraArgs = @()
  )

  $BundleMode = if ($OneDir) { "--onedir" } else { "--onefile" }
  $BuildRoot = Join-Path $env:TEMP "kapa-agent-pyinstaller"
  $WorkPath = Join-Path $BuildRoot "build-$Name"
  $SpecPath = Join-Path $BuildRoot "spec-$Name"
  New-Item -ItemType Directory -Force -Path $WorkPath | Out-Null
  New-Item -ItemType Directory -Force -Path $SpecPath | Out-Null

  Invoke-Checked -Name "pyinstaller build $Name" -Script {
    & $BuildPython -m PyInstaller `
      --clean `
      --noconfirm `
      $BundleMode `
      --name $Name `
      --distpath (Join-Path $SourceRoot "dist") `
      --workpath $WorkPath `
      --specpath $SpecPath `
      @CollectArgs `
      @ExtraArgs `
      (Join-Path $SourceRoot $EntryPoint)
  }
}

Build-Executable -Name $OutputName -EntryPoint "run_agent.py"
Build-Executable -Name "kapa-probe" -EntryPoint "run_probe.py" -ExtraArgs $ProbeDataArgs

$DistDir = Join-Path $SourceRoot "dist"
$PackageDir = Join-Path $DistDir "portable"
New-Item -ItemType Directory -Force -Path $PackageDir | Out-Null

if ($OneDir) {
  Copy-Item -Path (Join-Path $DistDir $OutputName) -Destination $PackageDir -Recurse -Force
  Copy-Item -Path (Join-Path $DistDir "kapa-probe") -Destination $PackageDir -Recurse -Force
} else {
  Copy-Item -Path (Join-Path $DistDir "$OutputName.exe") -Destination $PackageDir -Force
  Copy-Item -Path (Join-Path $DistDir "kapa-probe.exe") -Destination $PackageDir -Force
}
Copy-Item -Path (Join-Path $SourceRoot "config.example.json") -Destination $PackageDir -Force
Copy-Item -Path (Join-Path $SourceRoot "probe.config.example.json") -Destination $PackageDir -Force
Copy-Item -Path $ProbeConfigPath -Destination (Join-Path $PackageDir "probe.config.baked.json") -Force
Copy-Item -Path (Join-Path $SourceRoot "scripts\smoke-test.ps1") -Destination $PackageDir -Force
Copy-Item -Path (Join-Path $SourceRoot "scripts\run-probe.ps1") -Destination $PackageDir -Force
Copy-Item -Path (Join-Path $SourceRoot "scripts\run-probe-exe.ps1") -Destination $PackageDir -Force
Copy-Item -Path (Join-Path $SourceRoot "scripts\run-agent-exe.ps1") -Destination $PackageDir -Force
Copy-Item -Path (Join-Path $SourceRoot "scripts\install-exe-agent.ps1") -Destination $PackageDir -Force

$ZipPath = Join-Path $DistDir "$OutputName-portable.zip"
if (Test-Path $ZipPath) {
  Remove-Item $ZipPath -Force
}
Compress-Archive -Path (Join-Path $PackageDir "*") -DestinationPath $ZipPath

Write-Host "Built:"
if ($OneDir) {
  Write-Host "  $(Join-Path $DistDir $OutputName)"
  Write-Host "  $(Join-Path $DistDir "kapa-probe")"
} else {
  Write-Host "  $(Join-Path $DistDir "$OutputName.exe")"
  Write-Host "  $(Join-Path $DistDir "kapa-probe.exe")"
}
Write-Host "  $ZipPath"
