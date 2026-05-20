# MCP Server

Runs on the controller machine and exposes MCP tools that call the Windows
Agent over Tailscale.

## Configuration

```bash
export KAPA_AGENT_BASE_URL="http://100.x.y.z:8765"
export KAPA_AGENT_TOKEN="optional-shared-token"
```

## Local Run

```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install -e .
python -m kapa_mcp.server
```

## Tools

- `agent_health`
- `list_windows`
- `dump_uia`
- `send_hotkey`
- `type_text`
- `click_screen`
- `read_clipboard`
- `write_clipboard`
- `search_address`
- `run_recipe`
- `get_job`
- `list_artifacts`

High-level tools such as `search_address` are intentionally recipe-backed. Add
confirmed Windows steps to the agent's `config.local.json` after field
calibration.
