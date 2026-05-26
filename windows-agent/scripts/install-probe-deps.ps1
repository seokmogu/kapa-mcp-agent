param(
  [string]$Python = "py -3.11",
  [string]$VenvDir = ".venv",
  [switch]$SkipOptional,
  [switch]$NoIndex,
  [string]$FindLinks = ""
)

$ErrorActionPreference = "Stop"

$SourceRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $SourceRoot

$Report = [ordered]@{
  started_at = (Get-Date).ToString("o")
  source_root = $SourceRoot.Path
  python_command = $Python
  venv_dir = $VenvDir
  skip_optional = [bool]$SkipOptional
  no_index = [bool]$NoIndex
  find_links = $FindLinks
  steps = @()
}

function Add-Step {
  param(
    [string]$Name,
    [bool]$Ok,
    [string]$Output = "",
    [int]$ExitCode = 0
  )
  $Report.steps += [ordered]@{
    name = $Name
    ok = $Ok
    exit_code = $ExitCode
    output = $Output
  }
}

function Invoke-Capture {
  param(
    [string]$Name,
    [scriptblock]$Script
  )
  try {
    $Output = & $Script 2>&1 | Out-String
    Add-Step -Name $Name -Ok $true -Output $Output -ExitCode 0
    return $true
  } catch {
    $Output = ($_ | Out-String)
    if ($LASTEXITCODE -ne $null) {
      $Code = $LASTEXITCODE
    } else {
      $Code = 1
    }
    Add-Step -Name $Name -Ok $false -Output $Output -ExitCode $Code
    return $false
  }
}

Invoke-Capture -Name "windows_version" -Script {
  Get-CimInstance Win32_OperatingSystem |
    Select-Object Caption, Version, BuildNumber, OSArchitecture |
    ConvertTo-Json -Compress
} | Out-Null

Invoke-Capture -Name "python_version" -Script {
  Invoke-Expression "$Python --version"
} | Out-Null

$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
  Invoke-Capture -Name "create_venv" -Script {
    Invoke-Expression "$Python -m venv `"$VenvDir`""
  } | Out-Null
} else {
  Add-Step -Name "create_venv" -Ok $true -Output "venv already exists" -ExitCode 0
}

$PipBaseArgs = @()
if ($NoIndex) {
  $PipBaseArgs += "--no-index"
}
if ($FindLinks) {
  $PipBaseArgs += @("--find-links", $FindLinks)
}

Invoke-Capture -Name "upgrade_pip" -Script {
  & $VenvPython -m pip install @PipBaseArgs --upgrade pip wheel setuptools
} | Out-Null

$CoreOk = Invoke-Capture -Name "install_core_package" -Script {
  & $VenvPython -m pip install @PipBaseArgs -e .
}

if (-not $SkipOptional) {
  $OptionalOk = Invoke-Capture -Name "install_probe_extra" -Script {
    & $VenvPython -m pip install @PipBaseArgs -e ".[probe]"
  }
  if (-not $OptionalOk) {
    Invoke-Capture -Name "install_probe_optional_individually" -Script {
      & $VenvPython -m pip install @PipBaseArgs Pillow pywin32
    } | Out-Null
  }
}

Invoke-Capture -Name "probe_help" -Script {
  & $VenvPython -m kapa_agent.capability_probe --help
} | Out-Null

$Report.finished_at = (Get-Date).ToString("o")
$Report.core_install_ok = [bool]$CoreOk
$ReportPath = Join-Path $SourceRoot "install-probe-report.json"
$Report | ConvertTo-Json -Depth 6 | Set-Content -Path $ReportPath -Encoding UTF8

Write-Host "Wrote $ReportPath"
if (-not $CoreOk) {
  Write-Error "Core package install failed. See $ReportPath"
  exit 1
}
