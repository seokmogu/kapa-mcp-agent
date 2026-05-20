# Calibration Runbook

This is the first Windows field test. The goal is not to complete automation.
The goal is to decide which control and result-extraction paths work.

## 1. Start The Agent

On the Windows machine:

```powershell
cd C:\KapaAgent
.\.venv\Scripts\python.exe -m kapa_agent.main
```

Or start the scheduled task:

```powershell
schtasks /Run /TN KapaAgent
```

## 2. Run Local Smoke Test

```powershell
C:\KapaAgent\smoke-test.ps1 -BaseUrl "http://127.0.0.1:8765"
```

If a token is configured:

```powershell
C:\KapaAgent\smoke-test.ps1 `
  -BaseUrl "http://127.0.0.1:8765" `
  -Token "change-this"
```

Expected:

- `/health` succeeds.
- `/diagnostics` shows `pywinauto`, `pyperclip`, `mss`, and `psutil` available.
- `/windows` lists normal desktop windows.
- `/programs/kapa_hub_plus/probe` finds KAPA when it is open.
- screenshot may work or may show a high `black_ratio`; this is diagnostic only.

## 3. Run Controller Calibration

From the controller machine:

```bash
python3 tools/calibrate_agent.py \
  --base-url http://100.x.y.z:8765 \
  --token change-this \
  --program kapa_hub_plus
```

The script writes a JSON report with health, diagnostics, window list, program
probe, recent export files, screenshot metadata, and clipboard status.

## 4. Decide The Automation Path

Use this decision table:

| Observation | Meaning | Next step |
| --- | --- | --- |
| Program appears in `/windows` | Window discovery works | Dump UIA tree |
| Search controls appear in `/uia/dump` | UIA route is viable | Build recipe with selectors |
| Result table copies with `Ctrl+C` | Clipboard route is viable | Use `read_clipboard` artifacts |
| Exported XLSX/PDF appears in `/files/recent` | Export route is viable | Use file collection |
| Screenshot black ratio is high | Capture is blocked | Keep screenshot as diagnostic only |
| UIA, clipboard, and export all fail | Software automation is weak | Use IP-KVM for human operation |

## 5. Build The First Recipe

After confirming selectors, edit `C:\KapaAgent\config.local.json`:

```json
{
  "recipes": {
    "kapa_hub_plus.search_address": [
      {
        "action": "type_text",
        "text": "{{address}}",
        "paste": true,
        "submit": true,
        "selector": {
          "title_re": ".*(KAPA\\s*HUB|KAPA-HUB).*",
          "backend": "uia"
        }
      },
      {
        "action": "wait",
        "seconds": 3
      },
      {
        "action": "hotkey",
        "keys": "^a"
      },
      {
        "action": "hotkey",
        "keys": "^c"
      },
      {
        "action": "read_clipboard",
        "save_as": "clipboard"
      }
    ]
  }
}
```

Restart the agent after changing config.

