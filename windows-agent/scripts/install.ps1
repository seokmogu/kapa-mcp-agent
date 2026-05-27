<#
.SYNOPSIS
  Install (or reinstall) the KAPA Windows Agent from a GitHub release.

.DESCRIPTION
  Downloads the standalone kapa-agent.exe and kapa-watchdog.exe release assets
  directly (no zip), verifies each against its .sha256 sidecar, writes a
  config.local.json, best-effort seeds recipes/ from the repo, and optionally
  registers an ONLOGON scheduled task that runs the watchdog.

  No Python or build tools are needed on the target PC. Recipes can also be
  pulled later at runtime via POST /admin/update-recipes, so seeding is
  best-effort and a failure there does not fail the install.

.PARAMETER Repo
  owner/name of the GitHub repo holding the release. Default: seokmogu/kapa-mcp-agent

.PARAMETER Token
  Fine-grained read-only GitHub PAT. Only needed if the repo is PRIVATE
  (Contents: Read-only). Omit for a public repo. Stored in config.local.json
  so the agent can pull updates later.

.PARAMETER InstallDir   Where to install. Default: C:\KapaAgent
.PARAMETER Port         Local bind port. Default: 8765
.PARAMETER AgentToken   Optional shared token clients must send as X-Kapa-Agent-Token.
.PARAMETER RegisterTask Register an ONLOGON scheduled task 'KapaAgent'.
.PARAMETER SkipRecipes  Do not seed recipes/ at install time.

.EXAMPLE
  # Public repo one-liner (downloads exes only):
  & ([scriptblock]::Create((irm https://raw.githubusercontent.com/seokmogu/kapa-mcp-agent/main/windows-agent/scripts/install.ps1))) -RegisterTask

.EXAMPLE
  # Private repo:
  powershell -ExecutionPolicy Bypass -File install.ps1 -Token github_pat_xxx -RegisterTask
#>
param(
  [string]$Repo = "seokmogu/kapa-mcp-agent",
  [string]$Token = "",
  [string]$InstallDir = "C:\KapaAgent",
  [int]$Port = 8765,
  [string]$AgentToken = "",
  [switch]$RegisterTask,
  [switch]$SkipRecipes
)

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Get-Headers {
  param([string]$Accept = "application/vnd.github+json")
  $h = @{ "User-Agent" = "kapa-installer"; "X-GitHub-Api-Version" = "2022-11-28"; "Accept" = $Accept }
  if ($Token.Length -gt 0) { $h["Authorization"] = "Bearer $Token" }
  return $h
}

function Get-Asset {
  param($Release, [string]$Name)
  $a = $Release.assets | Where-Object { $_.name -eq $Name } | Select-Object -First 1
  if ($null -eq $a) { throw "Release $($Release.tag_name) has no asset '$Name'. Assets: $($Release.assets.name -join ', ')" }
  return $a
}

function Save-AssetVerified {
  param($Release, [string]$Name, [string]$Dest)
  $asset = Get-Asset $Release $Name
  Write-Host ("Downloading {0} ({1} MB) ..." -f $Name, [math]::Round($asset.size/1MB,1))
  Invoke-WebRequest -Uri $asset.url -Headers (Get-Headers "application/octet-stream") -OutFile $Dest

  $shaAsset = $Release.assets | Where-Object { $_.name -eq ($Name + ".sha256") } | Select-Object -First 1
  if ($null -ne $shaAsset) {
    $expected = (Invoke-WebRequest -Uri $shaAsset.url -Headers (Get-Headers "application/octet-stream")).Content.Trim().Split()[0].ToLower()
    $actual = (Get-FileHash $Dest -Algorithm SHA256).Hash.ToLower()
    if ($expected -ne $actual) { throw "Checksum mismatch for $Name`nexpected $expected`nactual   $actual" }
    Write-Host "  sha256 verified."
  } else {
    Write-Host "  (no .sha256 sidecar; skipping verification)"
  }
}

Write-Host "Querying latest release of $Repo ..."
$release = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest" -Headers (Get-Headers)
Write-Host "Found $($release.tag_name)"

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Save-AssetVerified $release "kapa-agent.exe"    (Join-Path $InstallDir "kapa-agent.exe")
Save-AssetVerified $release "kapa-watchdog.exe" (Join-Path $InstallDir "kapa-watchdog.exe")

# config.local.json (preserve an existing one)
$configPath = Join-Path $InstallDir "config.local.json"
if (-not (Test-Path $configPath)) {
  $config = [ordered]@{
    bind_host    = "127.0.0.1"
    port         = $Port
    artifact_dir = "artifacts"
    log_dir      = "logs"
    recipes_dir  = "recipes"
    auth_token   = $(if ($AgentToken.Length -gt 0) { $AgentToken } else { $null })
    github       = [ordered]@{
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

# Best-effort: seed recipes/ from the repo (active recipes only, skip templates).
if (-not $SkipRecipes) {
  try {
    $recipesDir = Join-Path $InstallDir "recipes"
    New-Item -ItemType Directory -Force -Path $recipesDir | Out-Null
    $listing = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/contents/recipes?ref=main" -Headers (Get-Headers)
    foreach ($item in $listing) {
      if ($item.name -like "*.json" -and $item.name -notlike "*.template.json") {
        Invoke-WebRequest -Uri $item.download_url -Headers (Get-Headers "application/vnd.github.raw") -OutFile (Join-Path $recipesDir $item.name)
        Write-Host "  seeded recipe: $($item.name)"
      }
    }
  } catch {
    Write-Host "  (recipe seeding skipped: $($_.Exception.Message). Pull later with POST /admin/update-recipes.)"
  }
}

if ($RegisterTask) {
  $watchdog = Join-Path $InstallDir "kapa-watchdog.exe"
  $action = New-ScheduledTaskAction -Execute $watchdog -WorkingDirectory $InstallDir
  $trigger = New-ScheduledTaskTrigger -AtLogOn
  $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
  Register-ScheduledTask -TaskName "KapaAgent" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
  Write-Host "Registered ONLOGON scheduled task 'KapaAgent'."
}

Write-Host ""
Write-Host "Installed to $InstallDir"
Write-Host "Start now:  `"$InstallDir\kapa-watchdog.exe`""
if ($RegisterTask) { Write-Host "Or:        schtasks /Run /TN KapaAgent" }
Write-Host "Verify:     curl http://127.0.0.1:$Port/health"
