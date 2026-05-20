param(
  [string]$BaseUrl = "http://127.0.0.1:8765",
  [string]$Token = ""
)

$ErrorActionPreference = "Stop"

function Invoke-Agent {
  param(
    [string]$Method,
    [string]$Path,
    [object]$Body = $null
  )

  $Headers = @{}
  if ($Token.Length -gt 0) {
    $Headers["X-Kapa-Agent-Token"] = $Token
  }

  $Uri = "$BaseUrl$Path"
  if ($null -eq $Body) {
    return Invoke-RestMethod -Method $Method -Uri $Uri -Headers $Headers
  }

  return Invoke-RestMethod `
    -Method $Method `
    -Uri $Uri `
    -Headers $Headers `
    -ContentType "application/json" `
    -Body ($Body | ConvertTo-Json -Depth 10)
}

Write-Host "Health"
Invoke-Agent -Method GET -Path "/health" | ConvertTo-Json -Depth 10

Write-Host "Diagnostics"
Invoke-Agent -Method GET -Path "/diagnostics" | ConvertTo-Json -Depth 10

Write-Host "Windows"
Invoke-Agent -Method GET -Path "/windows" | Select-Object -First 10 | ConvertTo-Json -Depth 10

Write-Host "KAPA probe"
Invoke-Agent -Method GET -Path "/programs/kapa_hub_plus/probe" | ConvertTo-Json -Depth 10

Write-Host "Recent export files"
Invoke-Agent `
  -Method POST `
  -Path "/files/recent" `
  -Body @{
    folders = @()
    patterns = @("*.xlsx", "*.xls", "*.csv", "*.pdf")
    minutes = 120
    limit = 20
  } | ConvertTo-Json -Depth 10

Write-Host "Diagnostic screenshot"
Invoke-Agent `
  -Method POST `
  -Path "/screen/screenshot" `
  -Body @{
    monitor = 1
    name = "smoke-test.png"
  } | ConvertTo-Json -Depth 10

