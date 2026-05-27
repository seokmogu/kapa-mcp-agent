"""Watchdog launcher for the KAPA Windows Agent.

Why this exists: a running EXE on Windows cannot overwrite itself. The agent's
POST /admin/update-agent stages a new binary as ``<asset>.new`` and drops a
``.update-pending`` marker. POST /admin/restart then exits the agent process.
This watchdog owns the agent process lifecycle, so when the agent exits it can:

  1. Apply any staged update (swap <asset>.new -> <asset>, archive the old one)
  2. Relaunch the agent

It supports two run modes, auto-detected:
  - frozen:  this watchdog is itself a PyInstaller EXE sitting next to
             ``kapa-agent.exe`` -> it launches that EXE.
  - source:  running from a source checkout -> it launches
             ``python -m kapa_agent.main``.

Pass --once to apply a pending update and start the agent a single time
(no relaunch loop) — useful for Task Scheduler ONLOGON setups that prefer the
scheduler to handle restarts.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def agent_command(base: Path, asset_name: str) -> list[str]:
    exe = base / asset_name
    if exe.exists():
        return [str(exe)]
    # source mode
    return [sys.executable, "-m", "kapa_agent.main"]


def apply_pending_update(base: Path, asset_name: str) -> str | None:
    marker = base / ".update-pending"
    staged = base / (asset_name + ".new")
    target = base / asset_name
    if not marker.exists() or not staged.exists():
        return None
    # archive the current binary if present
    if target.exists():
        archive = base / (asset_name + ".old")
        try:
            if archive.exists():
                archive.unlink()
            shutil.move(str(target), str(archive))
        except OSError:
            pass
    shutil.move(str(staged), str(target))
    try:
        marker.unlink()
    except OSError:
        pass
    return str(target)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="KAPA agent watchdog/launcher.")
    parser.add_argument("--asset-name", default=os.getenv("KAPA_AGENT_ASSET", "kapa-agent.exe"))
    parser.add_argument("--once", action="store_true", help="Run the agent once, do not relaunch.")
    parser.add_argument("--restart-delay", type=float, default=2.0)
    # any unknown args are forwarded to the agent command
    args, passthrough = parser.parse_known_args(argv)

    base = base_dir()
    while True:
        applied = apply_pending_update(base, args.asset_name)
        if applied:
            print(f"[watchdog] applied staged update -> {applied}", flush=True)

        cmd = agent_command(base, args.asset_name) + passthrough
        print(f"[watchdog] launching: {' '.join(cmd)}", flush=True)
        proc = subprocess.Popen(cmd, cwd=str(base))
        code = proc.wait()
        print(f"[watchdog] agent exited with code {code}", flush=True)

        if args.once:
            return code
        # if there's a pending update, loop immediately to apply+relaunch
        if (base / ".update-pending").exists():
            continue
        time.sleep(args.restart_delay)


if __name__ == "__main__":
    raise SystemExit(main())
