# Capability Probe

This is the first diagnostic program to run on a Windows PC that has KAPA HUB
PLUS or KAIS installed.

The goal is to answer one question:

> Which implementation channels are available on this PC and this program?

It does not try to automate business work. It does not click, type, submit,
inspect memory, bypass licensing, or extract credentials. It collects local
diagnostic evidence so the next recipe can be designed from real behavior.

## What It Checks

- Windows session and elevation state
- Optional dependency availability
- Top-level windows through ctypes, UIA, and Win32 backends
- Candidate KAPA/KAIS windows by title, process name, or class name
- Screen capture through multiple methods:
  - `mss`
  - `Pillow ImageGrab`
  - `pywin32` GDI desktop capture
  - `pywin32` `PrintWindow` capture for candidate windows
- Black-pixel ratio for each capture method
- Clipboard availability and hash/length
- Recent export-like files in Downloads, Documents, and Desktop
- UI Automation dumps for candidate windows
- A final `implementation_options` assessment

## Outputs

Each run creates:

- `capability-report.json`
- `capability-summary.md`
- `uia-dump-*.json` when candidate windows are found
- `kapa-capability-probe-<timestamp>.zip`

By default, the probe removes screenshot PNG files before creating the bundle
and does not include raw clipboard text. This keeps the first diagnostic run
small and less sensitive.

## Build The Double-Click EXE

For field delivery, build one EXE with the controller URL and token baked in:

```powershell
cd windows-agent\scripts
.\build-probe-exe.ps1 `
  -ProbePushUrl "http://100.a.b.c:8787/runs" `
  -ProbePushToken "change-this"
```

Send only:

```text
windows-agent\dist\kapa-probe.exe
```

The target user double-clicks `kapa-probe.exe`. It runs the probe, uploads the
result, shows a completion message, and leaves a local copy under `runs`.

## Build The Portable Package

Build this on a separate Windows build machine, not on the target PC:

```powershell
cd windows-agent\scripts
.\build-exe.ps1 -OneDir
```

Output:

```text
windows-agent\dist\kapa-agent-portable.zip
```

The target PC does not need Python. Copy and extract the ZIP.

## Portable Run On Target PC

Edit `probe.config.example.json`, save it as `probe.config.json`, then run:

```powershell
.\run-probe-exe.ps1
```

Or run the EXE directly:

```powershell
.\kapa-probe\kapa-probe.exe --config .\probe.config.json
```

If built without `-OneDir`, run:

```powershell
.\kapa-probe.exe --config .\probe.config.json
```

The probe automatically reads `probe.config.json` from the current folder or
next to the EXE.

Minimal `probe.config.json`:

```json
{
  "window_pattern": "(KAPA|HUB|KAIS)",
  "include_clipboard_text": false,
  "include_screenshot_files": false,
  "push_url": "http://100.a.b.c:8787/runs",
  "push_token": "change-this"
}
```

## Run With Python For Development

Use this only on a development or build machine:

```powershell
cd C:\KapaAgent\windows-agent
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[probe]"
.\scripts\run-probe.ps1
```

Or directly:

```powershell
.\.venv\Scripts\python.exe -m kapa_agent.capability_probe
```

Keep screenshots only when the operator is allowed to share what is visible on
screen:

```powershell
.\kapa-probe.exe --include-screenshot-files
```

Include clipboard text only when the operator has confirmed it is safe:

```powershell
.\kapa-probe.exe --include-clipboard-text
```

## Optional Push

Start the controller-side ingest server:

```powershell
python tools\ingest_server.py `
  --host 100.a.b.c `
  --port 8787 `
  --storage-dir runs `
  --token "change-this"
```

Use a Tailscale IP or another private address for `--host`.

Then run the probe on the target Windows PC:

```powershell
.\kapa-probe.exe `
  --push-url "http://100.a.b.c:8787/runs" `
  --push-token "change-this"
```

The probe sends the generated ZIP as a raw `application/zip` POST body. The
server stores the bundle, extracts it into a run folder, and writes
`metadata.json` so runs can be compared later.

Environment variables can be used instead of command-line arguments:

```powershell
$env:KAPA_PROBE_PUSH_URL = "http://100.a.b.c:8787/runs"
$env:KAPA_PROBE_PUSH_TOKEN = "change-this"
.\kapa-probe.exe
```

Until the ingest server is available, send back the generated ZIP manually.

## Antivirus And Trust

Keep the probe boring and transparent:

- Run it from a visible console or scheduled task that the operator knows about.
- Do not hide windows, obfuscate code, disable security tools, or request
  unnecessary admin privileges.
- Prefer a normal Python install or PyInstaller `onedir` package during early
  validation; single-file EXEs may be more likely to trigger heuristic scanning.
- Code-sign the final EXE or installer before field deployment.
- Use a fixed private controller URL and bearer token.
- Keep raw screenshot files and clipboard text disabled unless explicitly
  approved for that run.
- Store a copy of the generated `capability-summary.md` with the support ticket
  or field notes so the operator can see what was collected.

## Reading The Result

The summary includes a `Viability` value and `Options`.

- `screen_capture`: at least one capture method produced a non-black image.
- `uia`: UI Automation can see named controls in the candidate window.
- `clipboard`: clipboard read is available.
- `export_file_collection`: recent export-like files were found.

Preferred implementation order:

1. Export file collection
2. Clipboard extraction
3. UI Automation controls and recipes
4. Screen capture only as diagnostics
5. Hardware KVM/IP-KVM if every software path is blocked

## Re-run Pattern

Run the probe at these moments:

1. KAPA/KAIS closed
2. KAPA/KAIS login screen open
3. Main window open after login
4. After a manual search
5. Immediately after a manual Excel/PDF/export action

Comparing the bundles shows what changed and which channel is worth automating.

## Local Capture-Block Simulator

Before testing against KAPA/KAIS, validate the probe with the local simulator:

```powershell
python tools\protected_capture_test_app.py
```

The simulator opens a KAPA-like test window and calls Windows
`SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` so normal software capture
paths should miss or black out that window. It still exposes normal controls,
clipboard copy, and CSV export so the probe can prove that non-screenshot
channels remain useful.

In another PowerShell window, run:

```powershell
cd windows-agent
.\.venv\Scripts\python.exe -m kapa_agent.capability_probe `
  --window-pattern "KAPA HUB PLUS Capture Block Test" `
  --include-screenshot-files
```

Expected result:

- one or more capture methods may show a high black ratio or miss the protected
  window
- the candidate window should still be detected
- UIA or Win32 window metadata should provide useful structure
- pressing `표 복사` in the simulator before rerunning the probe should make the
  clipboard channel visible
- pressing `CSV 내보내기` before rerunning the probe should make recent export
  collection visible
