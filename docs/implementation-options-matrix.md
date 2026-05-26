# Implementation Options Matrix

KAPA/KAIS behavior is not known in advance, so the first implementation should
not bet on one remote-control technique. Build small probes for each channel,
run them on the authorized target PC, and choose the channel that survives.

## Channels To Test

| Channel | Probe evidence | If it works | If it fails |
| --- | --- | --- | --- |
| Full-screen capture via `mss` | `capture_methods[].method=mss_monitor_1` | Use screenshots for operator diagnostics | Ignore screenshots as primary data |
| Full-screen capture via `ImageGrab` | `pillow_imagegrab` | Compare with `mss` for black-window behavior | Keep disabled unless useful |
| GDI desktop capture | `pywin32_gdi_desktop` | Use as fallback capture path | Treat as blocked by app/OS path |
| Per-window `PrintWindow` | `pywin32_printwindow_*` | Use for targeted diagnostics | Do not rely on window pixels |
| Window discovery | `candidate_windows` | Anchor recipes by title/process/handle | Confirm app/session/permissions |
| UI Automation | `uia_dumps[].summary` | Build selectors and high-level recipes | Try Win32 backend/manual inspector |
| Clipboard | `clipboard.ok`, manual copy tests | Extract tables as text/HTML | Use export files or UIA |
| Export files | `recent_files` after manual export | Automate export and collect outputs | Fall back to clipboard/UIA |
| Absolute input | manual recipe smoke test | Use only for stable screens | Prefer selectors/hotkeys |
| Hardware KVM | manual observation | Last-resort visual channel | Keep software agent for files/logs |

## Decision Rules

- If export files appear reliably, make export collection the primary result
  path.
- If clipboard contains tabular data after manual copy, prefer clipboard over
  OCR.
- If UIA exposes stable names or AutomationIds, build recipes from selectors.
- If only coordinates work, keep recipes narrow and require frequent validation.
- If all software capture paths are black but UIA/clipboard/export works, ignore
  pixels and keep iterating.
- If capture, UIA, clipboard, and export all fail, use hardware KVM/IP-KVM for
  human operation and keep the agent as a file/log collector.

## What To Compare Across Runs

- capture method success and black ratio
- candidate window titles, handles, classes, and process names
- UIA control-type counts and search hits
- clipboard length/hash before and after manual copy
- recent export files before and after manual export
- changed fields in `capability-report.json`

The goal is not to identify KAPA internals first. The goal is to learn which
observable behavior is stable enough to automate.
