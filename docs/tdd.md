# Technical Design Document

## Purpose

Define the technical shape of the KAPA MCP Agent system before Windows field
implementation. This document focuses on architecture, components, data flow,
interfaces, packaging, and validation strategy.

## Architecture

```text
MCP Client
  -> mcp-server on controller
    -> HTTP over Tailscale/private network
      -> windows-agent in logged-in Windows desktop session
        -> KAPA HUB PLUS / KAIS
        -> UIA / keyboard / mouse / clipboard / export files
```

## Components

### Windows Agent

Location: `windows-agent/`

Responsibilities:

- Expose local HTTP API through FastAPI.
- Interact with desktop windows through pywinauto.
- Read and write clipboard text.
- Collect exported files.
- Capture optional diagnostic screenshots.
- Run configured recipes as asynchronous jobs.

Current implementation language:

- Python 3.11

Current key dependencies:

- FastAPI / uvicorn
- pywinauto
- pyperclip
- mss
- psutil
- watchdog
- pydantic

### MCP Server

Location: `mcp-server/`

Responsibilities:

- Expose MCP tools to clients.
- Translate MCP calls into Windows Agent HTTP calls.
- Keep target PC credentials/config out of prompts where possible.

Current implementation language:

- Python 3.11

Current key dependencies:

- MCP Python SDK
- httpx
- pydantic

### Recipes

Recipes are configured in `config.local.json` on the Windows machine.

Example:

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

## Data Flow

### Low-Level Calibration

```text
MCP client
  -> list_windows
  -> dump_uia
  -> type_text / send_hotkey / click_screen
  -> read_clipboard
  -> recent_export_files / collect_export_files
```

### High-Level Job

```text
MCP client
  -> search_address(address)
  -> Agent POST /jobs
  -> recipe execution
  -> clipboard/export result
  -> artifact storage
  -> MCP get_job/list_artifacts/read_artifact_text
```

## Session Model

The Agent must run in the interactive user session because Windows desktop
automation cannot reliably control GUI apps from Session 0 services.

Supported startup modes:

- Direct EXE execution
- Task Scheduler `ONLOGON`
- Future tray app/watchdog split

Unsupported as a primary path:

- Windows Service-only GUI automation

## Networking

Default:

- Bind host: `127.0.0.1`
- Port: `8765`

Remote private access:

- Bind host: Windows Tailscale IP
- Windows firewall allows only controller Tailscale IP
- Optional `X-Kapa-Agent-Token`

Public exposure:

- Not supported
- Do not use Tailscale Funnel for this Agent

## Packaging

Development run:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\python.exe -m kapa_agent.main
```

Portable run:

```powershell
.\kapa-agent.exe --host 127.0.0.1 --port 8765
```

Build:

```powershell
.\scripts\build-exe.ps1
```

The final x64 EXE should be built on x64 Windows if the target 업무 PC is x64.

## Error Handling

HTTP endpoints should return structured failure messages.

Job failures persist:

- job id
- task name
- failed status
- error text

Future improvements:

- step-level recipe trace artifacts
- screenshots only when available
- retry policy per action
- timeout per recipe step

## Security Boundary

This system assumes authorized local use on a permitted Windows machine.

Security posture:

- private Tailscale transport
- localhost default binding
- optional shared token
- local artifact storage
- no public tunnel

The Agent should not attempt to bypass target application security features.

## Future Technical Direction

### Python Agent Path

Keep Python if:

- pywinauto works on target
- PyInstaller packaging is acceptable
- recipes remain simple

### .NET/FlaUI Path

Move Agent core to .NET/FlaUI if:

- pywinauto is brittle
- UIA control patterns need stronger typed access
- EXE packaging/AV acceptance is easier with .NET
- Windows-native tray/watchdog behavior becomes important

### Hybrid Path

Keep MCP server in Python and implement a Windows-native Agent in C#.

```text
MCP Python server
  -> HTTP
    -> .NET FlaUI Agent
```

This is likely the best long-term production shape if target validation succeeds.

