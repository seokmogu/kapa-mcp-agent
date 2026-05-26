# Field Feedback Loop

This project should learn the target Windows program in small, auditable loops.

## Loop Shape

```text
Target Windows PC
  -> run capability probe
  -> push ZIP bundle to controller ingest server
  -> analyze report, UIA dumps, capture status, clipboard/export evidence
  -> update recipe/config or agent code
  -> redeploy to target PC
  -> run the probe again
```

The first loops are diagnostic only. They should not automate real work until
the available channels are known.

## Phase 1: Diagnose

First validate the tooling with the capture-block simulator:

```powershell
python tools\protected_capture_test_app.py
```

Then run `kapa-probe` against that simulator. This proves the loop can handle a
window where software screenshots are unreliable before touching the real target
program.

Run `kapa-probe` while KAPA/KAIS is:

1. closed
2. at login
3. at the main screen
4. after a manual search
5. immediately after a manual export

Compare the uploaded bundles. The useful signals are:

- whether capture methods are black or non-black
- whether the target window is visible to ctypes, Win32, or UIA
- whether UIA exposes named controls, buttons, menus, and tables
- whether clipboard read works
- whether export-like files appear after manual operations

## Phase 2: Pick A Channel

Prefer channels in this order:

1. export files
2. clipboard table extraction
3. UI Automation selectors
4. hotkeys and absolute clicks
5. screen capture only as diagnostics
6. hardware KVM/IP-KVM when software paths are blocked

## Phase 3: Recipe Iteration

Once a stable channel is found:

1. add or update a recipe in `config.local.json`
2. deploy the config to the target PC
3. run the recipe against a harmless test case
4. run `kapa-probe` again
5. compare outputs and refine selectors/actions

Prefer recipe/config changes over EXE changes. Rebuild the EXE only when the
agent needs a new capability.

## Ingest Server

Start a private ingest server on the controller:

```powershell
python tools\ingest_server.py `
  --host 100.a.b.c `
  --port 8787 `
  --storage-dir runs `
  --token "change-this"
```

Point the target probe at it:

```powershell
.\run-probe-exe.ps1
```

The portable folder should contain `probe.config.json` with `push_url` and
`push_token` set for the private controller.

Check received runs:

```powershell
Invoke-RestMethod "http://100.a.b.c:8787/runs"
```

## Guardrails

- Run only on authorized machines and accounts.
- Keep the desktop unlocked for GUI diagnostics.
- Do not capture raw clipboard text or screenshots unless the operator approves.
- Do not attempt to bypass licensing, authentication, endpoint security, or DRM.
- Keep controller access private, preferably over Tailscale or a VPN.
- Use code signing and documented install steps before broader deployment.
