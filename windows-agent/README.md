# Windows Agent

Runs in the logged-in Windows desktop session and exposes local automation APIs.

## Local Run

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
$env:KAPA_AGENT_BIND_HOST="127.0.0.1"
$env:KAPA_AGENT_PORT="8765"
.\.venv\Scripts\python.exe -m kapa_agent.main
```

Open:

```text
http://127.0.0.1:8765/docs
```

## Tailscale Run

Set `KAPA_AGENT_BIND_HOST` to the Windows machine's Tailscale IP, then restrict
the firewall so only the controller can reach the port.

```powershell
$env:KAPA_AGENT_BIND_HOST="100.x.y.z"
$env:KAPA_AGENT_PORT="8765"
.\.venv\Scripts\python.exe -m kapa_agent.main
```

## Important

Do not run only as a Windows Service. UI automation must run in the interactive
desktop session. Use Task Scheduler `ONLOGON` or a tray app/watchdog model.

## Single-File EXE

For a target PC where Python should not be installed, build on a separate
Windows sandbox:

```powershell
.\scripts\build-exe.ps1
```

Then copy `dist\kapa-agent-portable.zip` to the target PC. See
`..\docs\exe-build-and-install.md`.
