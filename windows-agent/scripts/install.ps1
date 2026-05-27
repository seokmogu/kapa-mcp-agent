<#
.SYNOPSIS
  Install (or reinstall) the KAPA Windows Agent from a GitHub release.

.DESCRIPTION
  Downloads the latest 'kapa-agent-portable.zip' release asset, extracts it to
  the install directory, writes a config.local.json (including the GitHub token
  so the agent can self-update later), and optionally registers an ONLOGON
  scheduled task that runs the watchdog.

  No Python or build tools are required on the target PC — the portable zip
  contains kapa-agent.exe and kapa-watchdog.exe.

.PARAMETER Repo
  owner/name of the GitHub repo holding the release. Default: seokmogu/kapa-mcp-agent

.PARAMETER Token
  Fine-grained read-only GitHub PAT. REQUIRED for a private repo (Contents:
  Read-only). Omit only if the repo/release is public. Stored in
  config.local.json so the agent can pull recipe/binary updates.

.PARAMETER InstallDir
  Where to install. Default: C:\KapaAgent

.PARAMETER Port
  Local bind port. Default: 8765

.PARAMETER AgentToken
  Optional shared token clients must send as X-Kapa-Agent-Token.

.PARAMETER RegisterTask
  Register an ONLOGON scheduled task 'KapaAgent' that runs the watchdog.

.EXAMPLE
  # Private repo (typical):
  powershell -ExecutionPolicy Bypass -File install.ps1 -Token github_pat_xxx -RegisterTask

.EXAMPLE
  # One-liner once this script is reachable (public repo):
  irm https://raw.githubusercontent.com/seokmogu/kapa-mcp-agent/main/windows-agent/scripts/install.ps1 | iex
#>
param(
  [string]$Repo = "seokmogu/kapa-mcp-agent",
  [string]$Token = "",
  [string]$InstallDir = "C:\KapaAgent",
  [int]$Port = 8765,
  [string]$AgentToken = "",
  [switch]$RegisterTask
)

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Get-Headers {
  $h = @{ "User-Agent" = "kapa-installer"; "X-GitHub-Api-Version" = "2022-11-28" }
  if ($Token.Length -gt 0) { $h["Authorization"] = "Bearer $Token" }
  return $h
}

Write-Host "Querying latest release of $Repo ..."
$headers = Get-Headers
$release = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest" -Headers $headers
$asset = $release.assets | Where-Object { $_.name -eq "kapa-agent-portable.zip" } | Select-Object -First 1
if ($null -eq $asset) {
  throw "Release $($release.tag_name) has no kapa-agent-portable.zip asset. Assets: $($release.assets.name -join ', ')"
}
Write-Host "Found $($release.tag_name) -> $($asset.name) ($([math]::Round($asset.size/1MB,1)) MB)"

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
$zip = Join-Path $InstallDir "portable.zip"

# Asset download needs the API asset URL + octet-stream accept (works for private repos).
$dlHeaders = Get-Headers
$dlHeaders["Accept"] = "application/octet-stream"
Write-Host "Downloading ..."
Invoke-WebRequest -Uri $asset.url -Headers $dlHeaders -OutFile $zip

Write-Host "Extracting to $InstallDir ..."
Expand-Archive -Path $zip -DestinationPath $InstallDir -Force
Remove-Item $zip -Force

# Write config.local.json (preserve an existing one if present).
$configPath = Join-Path $InstallDir "config.local.json"
if (-not (Test-Path $configPath)) {
  $config = [ordered]@{
    bind_host   = "127.0.0.1"
    port        = $Port
    artifact_dir = "artifacts"
    log_dir     = "logs"
    recipes_dir = "recipes"
    auth_token  = $(if ($AgentToken.Length -gt 0) { $AgentToken } else { $null })
    github      = [ordered]@{
      repo       = $Repo
      ref        = "main"
      token      = $(if ($Token.Length -gt 0) { $Token } else { $null })
      asset_name = "kapa-agent.exe"
    }
  }
  $config | ConvertTo-Json -Depth 6 | Set-Content -Path $configPath -Encoding UTF8
  Write-Host "Wrote $configPath"
} else {
  Write-Host "Kept existing $configPath"
}

if ($RegisterTask) {
  $watchdog = Join-Path $InstallDir "kapa-watchdog.exe"
  $taskName = "KapaAgent"
  $action = New-ScheduledTaskAction -Execute $watchdog -WorkingDirectory $InstallDir
  $trigger = New-ScheduledTaskTrigger -AtLogOn
  $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
  Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
  Write-Host "Registered ONLOGON scheduled task '$taskName'."
}

Write-Host ""
Write-Host "Installed to $InstallDir"
Write-Host "Start now:  `"$InstallDir\kapa-watchdog.exe`""
if ($RegisterTask) { Write-Host "Or:        schtasks /Run /TN KapaAgent" }
Write-Host "Verify:     curl http://127.0.0.1:$Port/health"
