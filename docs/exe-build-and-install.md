# Single EXE Probe Delivery

The field operator should receive one file:

```text
kapa-probe.exe
```

They should be able to double-click it. No Python install, package install,
ZIP extraction, config edit, or command-line work should be required.

## Build Machine Requirements

Build on a separate Windows machine:

- Python 3.11
- Internet access for build-time `pip install`
- this repository source folder

The target PC does not need any of these.

## Start The Ingest Server

On the controller machine:

```powershell
python tools\ingest_server.py `
  --host 100.a.b.c `
  --port 8787 `
  --storage-dir runs `
  --token "change-this"
```

Use a private Tailscale/VPN IP for `--host`.

## Build One Double-Click EXE

On the Windows build machine:

```powershell
cd windows-agent\scripts
.\build-probe-exe.ps1 `
  -ProbePushUrl "http://100.a.b.c:8787/runs" `
  -ProbePushToken "change-this" `
  -OutputDir "C:\KapaProbeBuild\dist"
```

For a Google Apps Script or similar Drive-ingest endpoint, build with:

```powershell
.\build-probe-exe.ps1 `
  -ProbePushUrl "https://script.google.com/macros/s/DEPLOYMENT_ID/exec" `
  -ProbePushToken "change-this" `
  -ProbePushFormat json-base64
```

Do not embed a Google user OAuth refresh token in the EXE. Use a private upload
endpoint that writes into Drive on the server side.

Output:

```text
windows-agent\dist\kapa-probe.exe
C:\KapaProbeBuild\dist\kapa-probe.exe
```

Send only that EXE to the target PC.

## Target PC Run

The operator double-clicks:

```text
kapa-probe.exe
```

The EXE will:

1. run the local capability probe
2. create a local result bundle under `runs`
3. upload the ZIP to the baked `ProbePushUrl`
4. show a completion message
5. write `runs\kapa-probe-last-run.txt`

If upload fails, the local ZIP remains in the `runs` folder next to the EXE.

## Optional Build Flags

Only enable these when approved for the specific run:

```powershell
.\build-probe-exe.ps1 `
  -ProbePushUrl "http://100.a.b.c:8787/runs" `
  -ProbePushToken "change-this" `
  -IncludeScreenshotFiles `
  -IncludeClipboardText
```

Default builds do not include raw screenshot files in the bundle and do not
include raw clipboard text.

## Trust And Endpoint Notes

- Do not hide the process or bypass endpoint tools.
- Build from a clean Windows build machine.
- Keep the final EXE output outside OneDrive/synced folders, for example
  `C:\KapaProbeBuild\dist`.
- Prefer code-signing the EXE before wider field use.
- The EXE writes visible output files and shows a completion message.
- The controller URL and token are baked into the EXE at build time.
- `raw-zip` upload is best for a private ingest server. `json-base64` is better
  for Google Apps Script style endpoints.
- If endpoint tools block one-file EXEs during testing, use the portable folder
  flow from `build-exe.ps1 -OneDir` as a fallback.
