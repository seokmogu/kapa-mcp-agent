# Tooling And Skills Research

This document records external tooling checked before Windows implementation.
Counts and update times were captured from GitHub search on 2026-05-21.

## Conclusion

Use our current repo as the domain-specific orchestration layer. Borrow ideas
from existing Windows automation MCP servers, but do not replace the project
with a generic MCP remote-control server.

Reason:

- Generic servers optimize for broad desktop control.
- This project needs KAPA/KAIS-specific recipes, result extraction, Tailscale
  deployment, artifact handling, and field calibration.

## Core References

### Official MCP Python SDK

URL:

https://github.com/modelcontextprotocol/python-sdk

Why relevant:

- Official Python SDK for MCP servers/clients.
- Current implementation uses `mcp.server.fastmcp.FastMCP`.

Decision:

- Keep for MCP bridge.

### Microsoft UI Automation

URL:

https://learn.microsoft.com/en-us/dotnet/framework/ui-automation/

Why relevant:

- UIA is the Windows-native accessibility and automation framework.
- pywinauto and FlaUI both sit on top of Windows automation concepts.

Decision:

- Use UIA as the conceptual base for selectors and diagnostics.

### pywinauto

URL:

https://github.com/pywinauto/pywinauto

Docs:

https://pywinauto.readthedocs.io/en/latest/getting_started.html

Why relevant:

- Fastest way to implement the Python Agent POC.
- Supports `backend="uia"` and `backend="win32"`.

Decision:

- Keep for POC.
- Reassess after KAPA/KAIS field calibration.

### FlaUI

URL:

https://github.com/FlaUI/FlaUI

GitHub snapshot:

- Stars: 2954
- License: MIT
- Updated: 2026-05-20

Why relevant:

- Mature .NET UI Automation library.
- Likely stronger long-term fit for Windows-native Agent.

Decision:

- Do not migrate yet.
- Keep as primary candidate if pywinauto is brittle or packaging is painful.

### FlaUInspect

URL:

https://github.com/FlaUI/FlaUInspect

Why relevant:

- UI inspection tool for field calibration.

Decision:

- Recommended Windows calibration tool.

## MCP Windows Automation Repositories

### mukul975/mcp-windows-automation

URL:

https://github.com/mukul975/mcp-windows-automation

GitHub snapshot:

- Stars: 23
- License: MIT
- Updated: 2026-05-20

Description:

AI-powered Windows Automation Server using MCP with many automation tools.

Assessment:

- Useful reference for breadth of MCP tool surface.
- Too generic for our target workflow.
- Could inspire diagnostics and command naming.

Decision:

- Reference only.

### sandraschi/pywinauto-mcp

URL:

https://github.com/sandraschi/pywinauto-mcp

GitHub snapshot:

- Stars: 16
- License: MIT
- Updated: 2026-05-20

Description:

Windows automation MCP server with webapp, pywinauto, screenshots, OCR, and
additional capabilities.

Assessment:

- Relevant because it combines pywinauto and MCP.
- Includes optional features not needed here.
- Repository topics mention keylogger, which is not aligned with this project.

Decision:

- Do not adopt directly.
- Inspect ideas only if needed.

### DaisukeHori/pywinauto-mcp

URL:

https://github.com/DaisukeHori/pywinauto-mcp

GitHub snapshot:

- Stars: 0
- Updated: 2026-04-30

Assessment:

- Small reference implementation.

Decision:

- Low priority.

### shanselman/FlaUI-MCP

URL:

https://github.com/shanselman/FlaUI-MCP

GitHub snapshot:

- Stars: 48
- License: MIT
- Updated: 2026-05-19

Description:

MCP server for Windows desktop automation using FlaUI and UI Automation APIs.

Assessment:

- Best reference if moving to .NET/FlaUI Agent.
- More aligned with Windows-native direction than pywinauto-only repos.

Decision:

- Review before any C# rewrite.

## Build And Packaging Tools

### PyInstaller

Use for current Python Agent single-EXE packaging.

Risk:

- One-file EXEs can trigger antivirus heuristics.
- Windows architecture matters: build x64 EXE on x64 Windows.

Fallback:

- Build `--onedir`.
- Move to .NET publish single-file.

## Skill Strategy

No external Codex skill should be installed yet.

Useful future skill ideas:

- Windows UIA calibration skill
- MCP server packaging skill
- PyInstaller Windows release skill
- FlaUI migration skill

For now, repo-local docs are enough. Installing generic external skills before
the real Windows calibration would add process without reducing uncertainty.

