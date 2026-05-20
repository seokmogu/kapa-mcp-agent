# Single-File EXE Build And Install

Use this when the target Windows PC should not have Python, SDKs, or developer
tools installed.

## Important Constraint

Build the EXE on a Windows sandbox/VM. PyInstaller does not reliably cross-build
Windows executables from macOS.

The target 업무 PC only needs:

- `kapa-agent.exe`
- optional `config.local.json`
- optional helper scripts for scheduled-task install and smoke test

## Build Machine Requirements

Install these only on the sandbox/build Windows machine:

- Python 3.11
- Git or a copied source folder
- Internet access for `pip install` during build

## Build

Open PowerShell in `windows-agent/scripts`:

```powershell
.\build-exe.ps1
```

Output:

```text
windows-agent\dist\kapa-agent.exe
windows-agent\dist\kapa-agent-portable.zip
```

## Run Directly On Target

Copy `kapa-agent-portable.zip` to the target Windows PC and extract it.

For localhost-only testing:

```powershell
.\kapa-agent.exe
```

Or with explicit options:

```powershell
.\kapa-agent.exe --host 127.0.0.1 --port 8765
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/health
```

## Install As Login Task

From the extracted portable folder:

```powershell
.\install-exe-agent.ps1 `
  -ExePath ".\kapa-agent.exe" `
  -InstallDir "C:\KapaAgent" `
  -BindHost "127.0.0.1" `
  -Port 8765
```

For Tailscale access:

```powershell
.\kapa-agent.exe `
  --host 100.x.y.z `
  --port 8765 `
  --token change-this
```

For scheduled login startup:

```powershell
.\install-exe-agent.ps1 `
  -ExePath ".\kapa-agent.exe" `
  -InstallDir "C:\KapaAgent" `
  -BindHost "100.x.y.z" `
  -Port 8765 `
  -ControllerIp "100.a.b.c" `
  -Token "change-this"
```

Then:

```powershell
schtasks /Run /TN KapaAgent
```

## Smoke Test

```powershell
C:\KapaAgent\smoke-test.ps1 `
  -BaseUrl "http://127.0.0.1:8765"
```

With token:

```powershell
C:\KapaAgent\smoke-test.ps1 `
  -BaseUrl "http://100.x.y.z:8765" `
  -Token "change-this"
```

## Notes

- The EXE must run in the logged-in desktop session, not only as a background
  service.
- If antivirus blocks one-file EXEs, build with PyInstaller `--onedir` as a
  fallback and copy the resulting folder.
- The EXE does not make screenshots the primary output path. It still prioritizes
  UI Automation, clipboard, and exported files.
