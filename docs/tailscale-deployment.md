# Tailscale Deployment

Use Tailscale only as the private transport. Do not use Funnel.

## Windows Agent Binding

For local testing:

```powershell
$env:KAPA_AGENT_BIND_HOST="127.0.0.1"
$env:KAPA_AGENT_PORT="8765"
```

For Tailscale access:

```powershell
$env:KAPA_AGENT_BIND_HOST="100.x.y.z"
$env:KAPA_AGENT_PORT="8765"
```

`100.x.y.z` is the Windows machine's Tailscale IP.

## Firewall Rule

Allow only the controller's Tailscale IP:

```powershell
New-NetFirewallRule `
  -DisplayName "Kapa Agent via Tailscale" `
  -Direction Inbound `
  -Action Allow `
  -Protocol TCP `
  -LocalPort 8765 `
  -RemoteAddress 100.a.b.c
```

## Install Example

Run from `windows-agent/scripts` in an elevated PowerShell:

```powershell
.\install-agent.ps1 `
  -InstallDir "C:\KapaAgent" `
  -BindHost "100.x.y.z" `
  -Port 8765 `
  -ControllerIp "100.a.b.c" `
  -Token "change-this"
```

Then from the controller:

```bash
curl -H 'X-Kapa-Agent-Token: change-this' http://100.x.y.z:8765/health
```

## MCP Environment

On the controller:

```bash
export KAPA_AGENT_BASE_URL="http://100.x.y.z:8765"
export KAPA_AGENT_TOKEN="change-this"
```

