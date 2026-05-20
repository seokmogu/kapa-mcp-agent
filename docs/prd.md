# Product Requirements Document

## Product Name

KAPA MCP Agent

## Problem

KAPA HUB PLUS / KAIS are Windows desktop 업무 프로그램. Existing remote-control
paths such as TeamViewer, Chrome Remote Desktop, screen sharing, and capture
tools may be blocked or produce black output. A screen-first remote-control
strategy is therefore unreliable.

The operator needs a private, local-to-Windows automation layer that can:

- Control the target program from an MCP client
- Run only on an authorized Windows desktop session
- Use Tailscale for private transport
- Recover structured results without depending on screenshots

## Goals

- Provide a Windows Agent that can be run as a single EXE.
- Expose low-level automation primitives for field calibration.
- Expose high-level recipe-backed actions for repeat workflows.
- Bridge the Agent to MCP tools.
- Prefer result extraction through UIA, clipboard, and exported files.
- Keep the target 업무 PC free of Python/dev tooling.

## Non-Goals

- Bypassing security controls in the target applications.
- Modifying, patching, or reverse engineering protected binaries.
- Public internet exposure.
- Building a general-purpose remote desktop product.
- Guaranteeing support before validation on the actual Windows target.

## Users

- Primary: operator controlling the authorized Windows 업무 PC.
- Secondary: developer calibrating selectors, recipes, and result parsers.
- MCP client: Codex/Claude/local operator console.

## Main Use Cases

### UC-1: Field Calibration

The developer runs the Agent on Windows, lists windows, probes KAPA/KAIS, dumps
UIA trees, tests keyboard/mouse input, checks clipboard extraction, and collects
recent export files.

### UC-2: Search Workflow Execution

The operator calls an MCP tool such as `search_address`. The MCP server sends a
job to the Windows Agent. The Agent executes a configured recipe, then returns a
job result and artifacts.

### UC-3: Export File Collection

The operator triggers or manually performs an export in the target app. The Agent
collects recent XLSX/PDF/CSV files from known folders and exposes them as
artifacts.

### UC-4: Troubleshooting

The operator requests health, diagnostics, program probe, screenshot black-ratio,
recent files, and clipboard state to determine why a workflow failed.

## Functional Requirements

### Agent

- `GET /health` returns runtime status.
- `GET /diagnostics` returns dependency and configuration status.
- `GET /windows` returns top-level windows visible to the interactive session.
- `GET /programs/{program}/probe` matches target program windows by configured
  title pattern.
- `POST /uia/dump` returns UI Automation tree data.
- `POST /input/type`, `/input/hotkey`, `/input/click` send user input.
- `GET /clipboard`, `POST /clipboard` read/write text clipboard.
- `POST /files/recent` lists likely export outputs.
- `POST /files/collect` copies export outputs into artifact storage.
- `POST /screen/screenshot` captures a diagnostic screenshot and black ratio.
- `POST /jobs` starts recipe-backed asynchronous work.
- `GET /jobs/{id}` returns job status/result.
- `GET /artifacts`, `GET /artifacts/{id}` list and fetch artifacts.

### MCP Server

- Exposes Agent functions as MCP tools.
- Reads `KAPA_AGENT_BASE_URL` and optional `KAPA_AGENT_TOKEN`.
- Supports low-level calibration tools.
- Supports high-level recipe tools such as `search_address`.

### Packaging

- Agent can run from source in a Windows development environment.
- Agent can be packaged as `kapa-agent.exe` via PyInstaller.
- Target PC deployment can use portable ZIP without Python install.

## Non-Functional Requirements

- Agent must run in the logged-in interactive desktop session.
- Agent should bind to `127.0.0.1` by default.
- Tailscale binding must be explicit.
- Optional shared token must be supported.
- Windows firewall should restrict Tailscale access to controller IP.
- Artifacts and logs must remain local unless explicitly fetched.
- Screenshots are diagnostic only, not the primary result channel.

## Acceptance Criteria

### POC Acceptance

- Agent starts on Windows and `/health` succeeds.
- `/windows` returns visible windows.
- Notepad can be controlled through type/hotkey APIs.
- Portable EXE can be built on Windows.
- MCP server can call the Agent over localhost or Tailscale.

### Target Acceptance

- KAPA HUB PLUS or KAIS appears in `/windows` or `/programs/{program}/probe`.
- At least one search workflow can be triggered.
- At least one result path works:
  - UIA table/text extraction
  - Clipboard copy
  - XLSX/PDF/CSV export collection
- A first recipe is saved in `config.local.json`.
- MCP can start the recipe and fetch the resulting artifact.

## Risks

- Target app may hide controls from UIA.
- Clipboard may not expose table data.
- Export features may be disabled by license/user role.
- Security/capture modules may detect automation tools.
- RDP/session lock may break interactive automation.
- PyInstaller one-file EXE may trigger antivirus heuristics.

## Open Questions

- Exact KAPA HUB PLUS executable/process name.
- Exact KAIS executable/process name.
- Whether target result grids support `Ctrl+C`.
- Whether export files are available without manual confirmation.
- Whether login/session state can be maintained safely.
- Whether target PC is x64 Windows and which Windows version.

