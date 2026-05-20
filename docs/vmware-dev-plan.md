# VMware-Based Windows Development Plan

## Short Answer

Yes. Use VMware Fusion on the Mac as the first Windows development sandbox.

However, this Mac is Apple Silicon (`arm64`), so the VMware guest should be
Windows 11 Arm. That is useful for development and first-pass testing, but it
does not completely replace testing on the real target Windows PC.

## What VMware Is Good For

Use a VMware Windows 11 Arm VM for:

- Building and exercising the Agent API shape
- Verifying FastAPI startup and endpoint behavior
- Testing PyInstaller packaging mechanics
- Testing the MCP server against a local Windows Agent
- Testing Task Scheduler login startup
- Testing Tailscale routing to the VM
- Testing UI Automation against simple Windows apps such as Notepad

This lets us iterate without touching the 업무 PC.

## What VMware Cannot Fully Prove

The VM cannot fully prove:

- Whether KAPA HUB PLUS / KAIS installs and runs in that environment
- Whether their security/capture modules behave the same as the real PC
- Whether UI Automation exposes the real program controls
- Whether clipboard/export behavior matches the real program
- Whether an ARM-built EXE works on an x64 target PC

The real KAPA/KAIS validation still has to happen on the Windows machine where
the programs are installed.

## Architecture Constraint

Apple Silicon VMware Fusion runs Arm guest operating systems. Windows 11 Arm can
run many x86/x64 user-mode applications through Windows compatibility layers,
but a PyInstaller build made with Arm Python will produce an Arm-oriented build.

If the target 업무 PC is Intel/AMD x64 Windows, the final portable EXE should be
built on x64 Windows. Options:

- A separate x64 Windows desktop/laptop
- A cloud x64 Windows VM
- An Intel Mac running x64 Windows VM
- The 업무 PC itself, only if installing build tools there is allowed

The preferred path remains:

```text
Mac VMware Fusion Windows 11 Arm VM
  -> develop and smoke-test
  -> validate API and MCP workflow

x64 Windows build VM or machine
  -> build final kapa-agent.exe for x64 target

target 업무 PC
  -> run portable EXE only
  -> no Python/dev tools
```

## Suggested VMware Workflow

1. Install VMware Fusion on Mac.
2. Create Windows 11 Arm VM.
3. Install Tailscale in the VM.
4. Copy this repo into the VM.
5. Build/run the agent in Python first.
6. Run `smoke-test.ps1`.
7. Build `kapa-agent.exe` with `scripts/build-exe.ps1`.
8. Test `kapa-agent.exe --host 127.0.0.1 --port 8765`.
9. Connect MCP server from Mac to the VM over Tailscale.
10. After this works, repeat final EXE build on x64 Windows if the target PC is x64.

## References

- VMware/Broadcom says Fusion Pro and Workstation Pro are available at no charge
  for commercial, educational, and personal use from supported current versions:
  https://knowledge.broadcom.com/external/article/368667/download-and-license-vmware-desktop-hype.html
- Broadcom notes that Apple Silicon Macs require Arm guest operating systems:
  https://knowledge.broadcom.com/external/article?legacyId=90364
- Broadcom notes Windows on Apple Silicon Fusion requires the Arm variant of
  Windows 11 and has known differences from x86 Windows:
  https://knowledge.broadcom.com/external/article?legacyId=95031

