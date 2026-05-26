"""End-to-end smoke test for a running KAPA Windows Agent.

Usage:
    python tools/agent_smoke.py [--base http://127.0.0.1:8765] [--token TOKEN]
                                [--out smoke_result.json] [--skip-notepad]

This script does not start the agent. Start it separately, then run this.
It exercises low-level primitives (health, diagnostics, /windows, files,
clipboard), a Notepad type/copy round-trip, /screen/screenshot, and the
recipe job machinery via the ``example.notepad_echo`` recipe defined in
config.example.json. A summary JSON is written to ``--out``.

It exits with code 0 if every step succeeded, otherwise 1 — making it
usable from build pipelines and from the smoke-test.ps1 wrapper.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _request(
    base: str,
    method: str,
    path: str,
    body: dict | None = None,
    token: str | None = None,
    timeout: float = 30.0,
) -> tuple[int, Any]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Kapa-Agent-Token"] = token
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, {"raw": raw}
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            payload = {"http_error_body": "<unreadable>"}
        return exc.code, payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", default="http://127.0.0.1:8765")
    parser.add_argument("--token", default=None)
    parser.add_argument(
        "--out",
        default=str(Path.cwd() / "smoke_result.json"),
        help="Where to write the JSON summary.",
    )
    parser.add_argument(
        "--skip-notepad",
        action="store_true",
        help="Skip the Notepad type/copy scenario (use on CI or headless boxes).",
    )
    parser.add_argument(
        "--echo-message",
        default="KAPA SMOKE 한글 OK",
        help="Text to type during the example.notepad_echo recipe.",
    )
    args = parser.parse_args(argv)

    base = args.base.rstrip("/")
    steps: list[dict[str, Any]] = []

    def step(name: str, fn) -> Any:
        started = time.time()
        try:
            value = fn()
            steps.append(
                {
                    "name": name,
                    "ok": True,
                    "value": value,
                    "duration_ms": round((time.time() - started) * 1000, 1),
                }
            )
            return value
        except Exception as exc:  # noqa: BLE001
            steps.append(
                {
                    "name": name,
                    "ok": False,
                    "error": repr(exc),
                    "duration_ms": round((time.time() - started) * 1000, 1),
                }
            )
            return None

    def get(path: str):
        status, body = _request(base, "GET", path, token=args.token)
        return {"status": status, "body": body}

    def post(path: str, payload: dict):
        status, body = _request(base, "POST", path, body=payload, token=args.token)
        return {"status": status, "body": body}

    step("health", lambda: get("/health"))
    step("diagnostics", lambda: get("/diagnostics"))

    def windows_summary():
        status, body = _request(base, "GET", "/windows", token=args.token)
        titles = [w.get("title") for w in (body or []) if isinstance(w, dict)]
        return {"status": status, "count": len(body or []), "titles": titles[:30]}

    step("list_windows", windows_summary)
    step("probe_kapa", lambda: get("/programs/kapa_hub_plus/probe"))
    step(
        "files_recent",
        lambda: post(
            "/files/recent",
            {
                "folders": [],
                "patterns": ["*.xlsx", "*.xls", "*.csv", "*.pdf"],
                "minutes": 1440,
                "limit": 5,
            },
        ),
    )

    step(
        "clipboard_roundtrip",
        lambda: (
            post("/clipboard", {"text": "kapa-smoke-clipboard"}),
            get("/clipboard"),
        ),
    )

    step("recipes_listed", lambda: get("/recipes"))

    if not args.skip_notepad:

        def notepad_scenario():
            proc = subprocess.Popen(["notepad.exe"], shell=False)
            try:
                time.sleep(1.5)
                # 1) direct primitives path
                primitives = {
                    "type": post(
                        "/input/type",
                        {
                            "text": args.echo_message + "\n",
                            "selector": {
                                "title_re": ".*(메모장|Notepad).*",
                                "backend": "uia",
                            },
                            "paste": True,
                            "submit": False,
                        },
                    ),
                    "select_all": post(
                        "/input/hotkey",
                        {
                            "keys": "^a",
                            "selector": {
                                "title_re": ".*(메모장|Notepad).*",
                                "backend": "uia",
                            },
                        },
                    ),
                    "copy": post(
                        "/input/hotkey",
                        {
                            "keys": "^c",
                            "selector": {
                                "title_re": ".*(메모장|Notepad).*",
                                "backend": "uia",
                            },
                        },
                    ),
                    "clipboard": get("/clipboard"),
                }
                # 2) recipe path (only meaningful if config has the recipe)
                recipe = post(
                    "/jobs",
                    {
                        "task": "run_recipe",
                        "params": {
                            "recipe": "example.notepad_echo",
                            "message": args.echo_message,
                        },
                        "outputs": ["clipboard"],
                    },
                )
                job_id = (recipe.get("body") or {}).get("id")
                final = None
                if job_id:
                    for _ in range(20):
                        time.sleep(0.5)
                        info = get(f"/jobs/{job_id}")
                        status = (info.get("body") or {}).get("status")
                        if status in ("succeeded", "failed"):
                            final = info
                            break
                return {"primitives": primitives, "recipe_job": recipe, "recipe_final": final}
            finally:
                subprocess.run(["taskkill", "/IM", "notepad.exe", "/F"], check=False)

        step("notepad_scenario", notepad_scenario)
    else:
        steps.append({"name": "notepad_scenario", "ok": True, "value": "skipped"})

    step(
        "screenshot",
        lambda: post("/screen/screenshot", {"monitor": 1, "name": "smoke.png"}),
    )

    summary: dict[str, Any] = {
        "base": base,
        "ok": all(s.get("ok") for s in steps),
        "step_count": len(steps),
        "fail_count": sum(1 for s in steps if not s.get("ok")),
        "steps": steps,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"smoke {'OK' if summary['ok'] else 'FAIL'} "
        f"({summary['step_count'] - summary['fail_count']}/{summary['step_count']} steps) "
        f"-> {out}"
    )
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
