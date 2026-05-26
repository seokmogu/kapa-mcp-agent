# KAPA MCP Agent

Local-only control stack for automating Windows desktop programs such as
KAPA HUB PLUS and KAIS through a Tailscale-private agent.

This project is intentionally split into two parts:

- `windows-agent/`: runs inside the logged-in Windows desktop session and
  performs UI automation, clipboard reads, file artifact collection, and
  workflow execution.
- `mcp-server/`: runs on the controller machine and exposes MCP tools that
  call the Windows Agent over Tailscale.

The current scaffold is designed for field validation. The public material and
the provided videos are enough to infer the program family and likely workflow,
but not enough to know exact UI Automation selectors. Those selectors must be
captured on the Windows machine where the programs are installed.

## What The Videos Show

The downloaded videos show a Windows desktop running:

- `KAPA HUB PLUS`, shown with the text "Korea Association of Property Appraisers".
- `부동산통합업무시스템`, likely KAIS in the appraisal workflow context.

Public references indicate that KAPA-HUB desktop is GIS-based and supports
location maps, map printing/splitting, property big-data comparison, related
information, and statistics. KAPA-HUB also links mobile field data back to the
desktop workflow.

References:

- KAPA HUB PLUS user training: https://edu.kapanet.or.kr/lecture.php?action=view&code=01&no=550
- KAPA-HUB desktop description in KAPA webzine: https://www.kapanet.or.kr/kapawebzine/data/136/sub/sub1_01_14.html

## Target Architecture

```text
Codex / Claude / operator console
  -> MCP server on controller machine
    -> Tailscale private HTTP
      -> Windows Agent in logged-in user session
        -> KAPA HUB PLUS / KAIS
        -> UIA / clipboard / export files / optional screenshots
```

Do not expose the agent to the public internet. Bind to `127.0.0.1` for local
testing, or to the Windows machine's Tailscale IP for private remote access.

## Validation Order

1. Install Tailscale on the controller and Windows machine.
2. Run `windows-agent` locally on the Windows machine.
3. Verify low-level tools:
   - `GET /windows`
   - `POST /uia/dump`
   - `POST /input/hotkey`
   - `POST /input/type`
   - `GET /clipboard`
4. Test KAPA/KAIS-specific actions manually through low-level APIs.
5. Convert the confirmed steps into a JSON recipe.
6. Expose the recipe as a high-level MCP tool.

Use [docs/calibration-runbook.md](docs/calibration-runbook.md) for the first
field test.

For a target Windows PC with no developer tooling, build a single double-click
probe EXE on a separate Windows sandbox and send only that file. See
[docs/exe-build-and-install.md](docs/exe-build-and-install.md).

Before implementing a workflow recipe, run the local diagnostic probe on the
target Windows PC to learn which channels are available. See
[docs/capability-probe.md](docs/capability-probe.md).
For the repeated diagnose/analyze/update cycle, see
[docs/feedback-loop.md](docs/feedback-loop.md).
For the channel-by-channel decision matrix, see
[docs/implementation-options-matrix.md](docs/implementation-options-matrix.md).
For Google Drive style upload, see
[docs/google-drive-ingest.md](docs/google-drive-ingest.md).

For VMware-based Windows development on this Mac, see
[docs/vmware-dev-plan.md](docs/vmware-dev-plan.md).

Korean project summary and next-step plan:
[docs/project-brief-ko.md](docs/project-brief-ko.md).

Public target research collected before Windows field testing:
[docs/target-research-dossier.md](docs/target-research-dossier.md) and
[docs/public-image-inventory.md](docs/public-image-inventory.md).

Planning and engineering docs:
[docs/prd.md](docs/prd.md),
[docs/tdd.md](docs/tdd.md),
[docs/spec.md](docs/spec.md),
[docs/test-plan.md](docs/test-plan.md), and
[docs/tooling-and-skills-research.md](docs/tooling-and-skills-research.md).

## Why Not Screenshot First?

The videos suggest that normal capture/remote-control tools may be blacked out.
This scaffold therefore treats screenshots as optional diagnostics only. The
main data collection paths are:

- Windows UI Automation tree and control values
- Clipboard text/HTML after table copy operations
- Program export files such as XLSX/PDF/CSV
- Local files/cache where legally accessible
- Network metadata only when needed

## Quick Start

Windows Agent:

```powershell
cd windows-agent
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
$env:KAPA_AGENT_BIND_HOST="127.0.0.1"
$env:KAPA_AGENT_PORT="8765"
.\.venv\Scripts\python.exe -m kapa_agent.main
```

MCP Server:

```bash
cd mcp-server
python3.11 -m venv .venv
. .venv/bin/activate
pip install -e .
export KAPA_AGENT_BASE_URL="http://100.x.y.z:8765"
python -m kapa_mcp.server
```

Replace `100.x.y.z` with the Windows machine's Tailscale IP.
