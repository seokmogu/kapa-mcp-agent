# Test Plan

## Test Levels

### L0: Static Checks

Run on macOS or Windows:

```bash
python3 -m compileall windows-agent mcp-server tools
```

Expected:

- No syntax errors.

### L1: Windows Development Smoke Test

Run on Windows with Python installed:

```powershell
cd windows-agent
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\python.exe -m kapa_agent.main
```

In another PowerShell:

```powershell
.\scripts\smoke-test.ps1 -BaseUrl "http://127.0.0.1:8765"
```

Expected:

- `/health` succeeds.
- `/diagnostics` reports dependencies available.
- `/windows` returns windows.

### L2: Notepad Automation

Purpose:

Validate automation primitives without target app access.

Steps:

1. Open Notepad.
2. Call `/windows` and find Notepad title.
3. Call `/input/type` with text.
4. Call `/input/hotkey` with `^a`, then `^c`.
5. Call `/clipboard`.

Expected:

- Clipboard matches typed text.

### L3: EXE Packaging

Run on Windows:

```powershell
cd windows-agent\scripts
.\build-exe.ps1
```

Expected:

- `dist\kapa-agent.exe` exists.
- `dist\kapa-agent-portable.zip` exists.
- EXE starts and `/health` succeeds.

### L4: Tailscale Connectivity

Run Agent on Windows:

```powershell
.\kapa-agent.exe --host 100.x.y.z --port 8765 --token change-this
```

Run from controller:

```bash
curl -H 'X-Kapa-Agent-Token: change-this' http://100.x.y.z:8765/health
```

Expected:

- Controller can access Agent.
- Non-controller hosts are blocked by Windows firewall or Tailscale ACL.

### L5: MCP Bridge

Run MCP server with:

```bash
export KAPA_AGENT_BASE_URL="http://100.x.y.z:8765"
export KAPA_AGENT_TOKEN="change-this"
python -m kapa_mcp.server
```

Expected:

- `agent_health` succeeds.
- `list_windows` returns Windows data.

### L6: KAPA/KAIS Field Calibration

Steps:

1. Start KAPA HUB PLUS.
2. Run `probe_program`.
3. Dump UIA tree.
4. Search UIA dump for keywords from `target-research-dossier.md`.
5. Manually run one search.
6. Test clipboard extraction.
7. Test export collection.
8. Test diagnostic screenshot black ratio.

Expected:

- At least one result extraction path succeeds.

### L7: First Recipe

Steps:

1. Add `kapa_hub_plus.search_address` to `config.local.json`.
2. Restart Agent.
3. Call MCP `search_address`.
4. Poll job.
5. Fetch artifact.

Expected:

- Job succeeds.
- Artifact contains structured result text or exported file reference.

## Regression Matrix

| Area | Test |
| --- | --- |
| Agent startup | `/health`, `/diagnostics` |
| UIA | `/windows`, `/uia/dump` |
| Input | Notepad type/hotkey |
| Clipboard | copy/read roundtrip |
| Files | create local CSV/PDF dummy and collect |
| Screenshot | screenshot returns artifact and black ratio |
| Jobs | run recipe with Notepad or clipboard |
| MCP | health/list windows/job polling |
| Packaging | EXE build and direct run |

## Failure Triage

- `/windows` empty: Agent is not in interactive session.
- UIA dump fails: wrong backend or window selector.
- Typing fails: target focus problem or blocked input.
- Clipboard empty: target grid does not support copy or focus is wrong.
- Files not found: export folder/pattern wrong.
- Screenshot black: expected in protected environments; use non-screen paths.
- MCP fails but Agent works: controller env vars or token mismatch.

