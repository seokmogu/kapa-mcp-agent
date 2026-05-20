#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect a first-pass calibration report from KAPA Agent.")
    parser.add_argument("--base-url", required=True, help="Agent base URL, e.g. http://100.x.y.z:8765")
    parser.add_argument("--token", default="", help="Optional X-Kapa-Agent-Token")
    parser.add_argument("--program", default="kapa_hub_plus", help="Program key to probe")
    parser.add_argument("--out", default="", help="Output JSON file")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    headers = {}
    if args.token:
        headers["X-Kapa-Agent-Token"] = args.token

    report: dict[str, Any] = {
        "base_url": base_url,
        "program": args.program,
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "checks": {},
    }

    for name, method, path, body in [
        ("health", "GET", "/health", None),
        ("diagnostics", "GET", "/diagnostics", None),
        ("windows", "GET", "/windows", None),
        ("program_probe", "GET", f"/programs/{args.program}/probe", None),
        ("recent_files", "POST", "/files/recent", {"folders": [], "patterns": ["*.xlsx", "*.xls", "*.csv", "*.pdf"], "minutes": 120, "limit": 20}),
        ("screenshot", "POST", "/screen/screenshot", {"monitor": 1, "name": "calibration_screenshot.png"}),
        ("clipboard", "GET", "/clipboard", None),
    ]:
        report["checks"][name] = request_json(base_url, headers, method, path, body)

    out = Path(args.out) if args.out else Path(f"kapa-agent-calibration-{int(time.time())}.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out)
    return 0


def request_json(
    base_url: str,
    headers: dict[str, str],
    method: str,
    path: str,
    body: dict[str, Any] | None,
) -> dict[str, Any]:
    data = None
    request_headers = dict(headers)
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        base_url + path,
        data=data,
        headers=request_headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = response.read().decode("utf-8", errors="replace")
        return {
            "ok": True,
            "status": response.status,
            "data": json.loads(payload) if payload else None,
        }
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "status": exc.code,
            "error": exc.read().decode("utf-8", errors="replace"),
        }
    except Exception as exc:  # noqa: BLE001 - calibration must keep going
        return {
            "ok": False,
            "error": str(exc),
        }


if __name__ == "__main__":
    sys.exit(main())

