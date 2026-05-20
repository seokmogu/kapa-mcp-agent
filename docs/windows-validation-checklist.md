# Windows Validation Checklist

Run this on the Windows PC that has KAPA HUB PLUS / KAIS installed.

## 1. Session Requirements

- Log in as the user who normally runs the target programs.
- Keep the desktop unlocked during automation tests.
- Avoid running the agent only as a Windows Service. GUI automation must run in
  the interactive user session.
- Confirm Tailscale is connected and note the Tailscale IP.

## 2. Inspect UI Automation

Install at least one inspector:

- Accessibility Insights for Windows
- FlaUInspect
- Microsoft Inspect.exe from the Windows SDK

For each program, record:

- Main window title
- Process name
- Login field names/AutomationIds
- Search box names/AutomationIds
- Search button names/AutomationIds
- Result table control type
- Whether table rows expose text through UIA

## 3. Test Clipboard Extraction

For each result table:

1. Click the result table.
2. Press `Ctrl+A`.
3. Press `Ctrl+C`.
4. Read clipboard text through the agent.
5. Check whether the copied data is plain text, HTML, or empty.

## 4. Test Export Paths

Record whether these exist and where files are created:

- Excel export
- CSV export
- PDF output
- Print preview
- Report save
- Map image save

Watch folders:

- `%USERPROFILE%\Downloads`
- `%USERPROFILE%\Documents`
- Program-specific output folders
- Desktop

## 5. Minimum Success Criteria

Automation is viable when all of these are true:

- The agent can find the main program window.
- Text input works in at least one search workflow.
- Search execution can be triggered by button, hotkey, or Enter.
- Results can be collected by UIA, clipboard, or export file.

If all result paths fail, use an IP-KVM for human control and keep this agent for
file/clipboard collection only.

