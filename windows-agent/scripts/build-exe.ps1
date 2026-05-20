param(
  [string]$Python = "py -3.11",
  [string]$OutputName = "kapa-agent"
)

$ErrorActionPreference = "Stop"

$SourceRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $SourceRoot

$BuildVenv = Join-Path $SourceRoot ".build-venv"
if (-not (Test-Path (Join-Path $BuildVenv "Scripts\python.exe"))) {
  Invoke-Expression "$Python -m venv `"$BuildVenv`""
}

$BuildPython = Join-Path $BuildVenv "Scripts\python.exe"
& $BuildPython -m pip install --upgrade pip wheel setuptools
& $BuildPython -m pip install pyinstaller
& $BuildPython -m pip install .

$CollectArgs = @(
  "--collect-submodules", "pywinauto",
  "--collect-submodules", "comtypes",
  "--collect-submodules", "uvicorn",
  "--collect-submodules", "fastapi",
  "--collect-submodules", "pydantic",
  "--collect-submodules", "starlette",
  "--collect-submodules", "anyio",
  "--collect-submodules", "mss",
  "--collect-submodules", "psutil",
  "--collect-submodules", "pyperclip",
  "--hidden-import", "win32timezone"
)

& $BuildPython -m PyInstaller `
  --clean `
  --noconfirm `
  --onefile `
  --name $OutputName `
  @CollectArgs `
  (Join-Path $SourceRoot "run_agent.py")

$DistDir = Join-Path $SourceRoot "dist"
$PackageDir = Join-Path $DistDir "portable"
New-Item -ItemType Directory -Force -Path $PackageDir | Out-Null

Copy-Item -Path (Join-Path $DistDir "$OutputName.exe") -Destination $PackageDir -Force
Copy-Item -Path (Join-Path $SourceRoot "config.example.json") -Destination $PackageDir -Force
Copy-Item -Path (Join-Path $SourceRoot "scripts\smoke-test.ps1") -Destination $PackageDir -Force
Copy-Item -Path (Join-Path $SourceRoot "scripts\run-agent-exe.ps1") -Destination $PackageDir -Force
Copy-Item -Path (Join-Path $SourceRoot "scripts\install-exe-agent.ps1") -Destination $PackageDir -Force

$ZipPath = Join-Path $DistDir "$OutputName-portable.zip"
if (Test-Path $ZipPath) {
  Remove-Item $ZipPath -Force
}
Compress-Archive -Path (Join-Path $PackageDir "*") -DestinationPath $ZipPath

Write-Host "Built:"
Write-Host "  $(Join-Path $DistDir "$OutputName.exe")"
Write-Host "  $ZipPath"

