#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_SEARCH_TERMS = [
    "KAPA",
    "HUB",
    "KAIS",
    "Excel",
    "XLS",
    "CSV",
    "PDF",
    "print",
    "export",
    "save",
    "copy",
    "search",
    "address",
]

DEFAULT_WINDOW_PATTERN = r"(KAPA|HUB|KAIS)"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect a non-invasive field reconnaissance report from KAPA Windows Agent."
    )
    parser.add_argument("--base-url", required=True, help="Agent base URL, e.g. http://100.x.y.z:8765")
    parser.add_argument("--token", default="", help="Optional X-Kapa-Agent-Token")
    parser.add_argument("--program", default="kapa_hub_plus", help="Configured program key to probe")
    parser.add_argument("--backend", default="uia", choices=["uia", "win32"], help="pywinauto backend")
    parser.add_argument("--max-depth", type=int, default=7, help="Maximum UIA tree depth per candidate")
    parser.add_argument("--max-nodes", type=int, default=1200, help="Maximum UIA nodes per candidate")
    parser.add_argument(
        "--window-pattern",
        default=DEFAULT_WINDOW_PATTERN,
        help="Case-insensitive regex for extra candidate top-level windows",
    )
    parser.add_argument(
        "--search-term",
        action="append",
        default=[],
        help="Term to highlight in UIA dumps. May be repeated.",
    )
    parser.add_argument("--out-dir", default="", help="Directory for JSON, markdown, and downloaded artifacts")
    parser.add_argument("--skip-screenshot", action="store_true", help="Do not call /screen/screenshot")
    parser.add_argument("--download-artifacts", action="store_true", help="Download screenshot/text artifacts by id")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    headers = {}
    if args.token:
        headers["X-Kapa-Agent-Token"] = args.token

    out_dir = Path(args.out_dir) if args.out_dir else Path(f"kapa-field-recon-{int(time.time())}")
    out_dir.mkdir(parents=True, exist_ok=True)

    terms = args.search_term or DEFAULT_SEARCH_TERMS
    report: dict[str, Any] = {
        "base_url": base_url,
        "program": args.program,
        "backend": args.backend,
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "search_terms": terms,
        "checks": {},
        "candidate_windows": [],
        "uia_dumps": [],
        "downloads": [],
        "assessment": {},
    }

    for name, method, path, body in [
        ("health", "GET", "/health", None),
        ("diagnostics", "GET", "/diagnostics", None),
        ("windows", "GET", "/windows", None),
        ("program_probe", "GET", f"/programs/{args.program}/probe?backend={args.backend}", None),
        (
            "recent_files",
            "POST",
            "/files/recent",
            {
                "folders": [],
                "patterns": ["*.xlsx", "*.xls", "*.csv", "*.pdf", "*.hwp", "*.hwpx"],
                "minutes": 240,
                "limit": 50,
            },
        ),
        ("clipboard", "GET", "/clipboard", None),
    ]:
        report["checks"][name] = request_json(base_url, headers, method, path, body)

    if not args.skip_screenshot:
        report["checks"]["screenshot"] = request_json(
            base_url,
            headers,
            "POST",
            "/screen/screenshot",
            {"monitor": 1, "name": "field_recon_screenshot.png"},
        )

    windows = data_from_check(report["checks"].get("windows"))
    probe = data_from_check(report["checks"].get("program_probe"))
    candidates = select_candidates(windows, probe, args.window_pattern)
    report["candidate_windows"] = candidates

    for index, window in enumerate(candidates):
        selector = selector_for_window(window, args.backend)
        dump_check = request_json(
            base_url,
            headers,
            "POST",
            "/uia/dump",
            {
                "selector": selector,
                "max_depth": args.max_depth,
                "max_nodes": args.max_nodes,
            },
        )
        entry = {
            "index": index,
            "window": window,
            "selector": selector,
            "dump": dump_check,
        }
        if dump_check.get("ok"):
            summary = summarize_uia_tree(dump_check.get("data"), terms)
            entry["summary"] = summary
            dump_path = out_dir / f"uia-dump-{index + 1}.json"
            dump_path.write_text(json.dumps(dump_check.get("data"), ensure_ascii=False, indent=2), encoding="utf-8")
            entry["dump_file"] = str(dump_path)
        report["uia_dumps"].append(entry)

    if args.download_artifacts:
        report["downloads"] = download_known_artifacts(base_url, headers, report, out_dir)

    report["assessment"] = assess(report)

    json_path = out_dir / "field-recon-report.json"
    markdown_path = out_dir / "field-recon-summary.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")

    print(json_path)
    print(markdown_path)
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
        with urllib.request.urlopen(request, timeout=25) as response:
            payload = response.read().decode("utf-8", errors="replace")
            status = response.status
        return {
            "ok": True,
            "status": status,
            "data": json.loads(payload) if payload else None,
        }
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "status": exc.code,
            "error": exc.read().decode("utf-8", errors="replace"),
        }
    except Exception as exc:  # noqa: BLE001 - field reports should keep partial results
        return {
            "ok": False,
            "error": str(exc),
        }


def request_bytes(base_url: str, headers: dict[str, str], path: str) -> dict[str, Any]:
    request = urllib.request.Request(base_url + path, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return {
                "ok": True,
                "status": response.status,
                "data": response.read(),
            }
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "status": exc.code,
            "error": exc.read().decode("utf-8", errors="replace"),
        }
    except Exception as exc:  # noqa: BLE001 - field reports should keep partial results
        return {
            "ok": False,
            "error": str(exc),
        }


def data_from_check(check: dict[str, Any] | None) -> Any:
    if not check or not check.get("ok"):
        return None
    return check.get("data")


def select_candidates(
    windows: Any,
    probe: Any,
    window_pattern: str,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[Any, str]] = set()

    if isinstance(probe, dict):
        for item in probe.get("matches", []) or []:
            add_candidate(candidates, seen, item, "program_probe")

    regex = re.compile(window_pattern, re.IGNORECASE)
    if isinstance(windows, list):
        for item in windows:
            title = str(item.get("title", "") if isinstance(item, dict) else "")
            process_name = str(item.get("process_name", "") if isinstance(item, dict) else "")
            if regex.search(title) or regex.search(process_name):
                add_candidate(candidates, seen, item, "window_pattern")

    return candidates


def add_candidate(
    candidates: list[dict[str, Any]],
    seen: set[tuple[Any, str]],
    item: Any,
    reason: str,
) -> None:
    if not isinstance(item, dict):
        return
    key = (item.get("handle"), item.get("title", ""))
    if key in seen:
        return
    seen.add(key)
    candidate = dict(item)
    candidate["candidate_reason"] = reason
    candidates.append(candidate)


def selector_for_window(window: dict[str, Any], backend: str) -> dict[str, Any]:
    handle = window.get("handle")
    if isinstance(handle, int) and handle > 0:
        return {"handle": handle, "backend": backend}
    title = str(window.get("title", ""))
    return {"title_re": re.escape(title), "backend": backend}


def summarize_uia_tree(tree: Any, terms: list[str]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "node_count": 0,
        "max_depth_seen": 0,
        "control_types": {},
        "named_controls": [],
        "search_hits": [],
    }
    controls: Counter[str] = Counter()

    def walk(node: Any, depth: int, path: str) -> None:
        if not isinstance(node, dict):
            return
        summary["node_count"] += 1
        summary["max_depth_seen"] = max(summary["max_depth_seen"], depth)
        control_type = str(node.get("control_type") or "")
        if control_type:
            controls[control_type] += 1
        name = str(node.get("name") or "")
        automation_id = str(node.get("automation_id") or "")
        class_name = str(node.get("class_name") or "")
        text = " ".join([name, automation_id, class_name, control_type])

        if name or automation_id:
            named = {
                "path": path,
                "name": name,
                "control_type": control_type,
                "automation_id": automation_id,
                "class_name": class_name,
                "rectangle": node.get("rectangle"),
            }
            if len(summary["named_controls"]) < 120:
                summary["named_controls"].append(named)

        for term in terms:
            if term and term.lower() in text.lower():
                summary["search_hits"].append(
                    {
                        "term": term,
                        "path": path,
                        "name": name,
                        "control_type": control_type,
                        "automation_id": automation_id,
                        "class_name": class_name,
                    }
                )

        for child_index, child in enumerate(node.get("children", []) or []):
            child_name = str(child.get("name", "") if isinstance(child, dict) else "")
            child_path = f"{path}/{child_index}:{shorten(child_name, 40)}"
            walk(child, depth + 1, child_path)

    walk(tree, 0, "root")
    summary["control_types"] = dict(controls.most_common())
    summary["search_hits"] = summary["search_hits"][:200]
    return summary


def download_known_artifacts(
    base_url: str,
    headers: dict[str, str],
    report: dict[str, Any],
    out_dir: Path,
) -> list[dict[str, Any]]:
    downloads = []
    screenshot = data_from_check(report["checks"].get("screenshot"))
    artifact = screenshot.get("artifact") if isinstance(screenshot, dict) else None
    if isinstance(artifact, dict) and artifact.get("id"):
        downloads.append(download_artifact(base_url, headers, artifact, out_dir))
    return downloads


def download_artifact(
    base_url: str,
    headers: dict[str, str],
    artifact: dict[str, Any],
    out_dir: Path,
) -> dict[str, Any]:
    artifact_id = str(artifact["id"])
    name = sanitize_filename(str(artifact.get("name") or f"{artifact_id}.bin"))
    result = request_bytes(base_url, headers, f"/artifacts/{artifact_id}")
    if not result.get("ok"):
        return {
            "ok": False,
            "artifact_id": artifact_id,
            "name": name,
            "error": result.get("error"),
            "status": result.get("status"),
        }
    path = out_dir / name
    path.write_bytes(result["data"])
    return {
        "ok": True,
        "artifact_id": artifact_id,
        "name": name,
        "path": str(path),
        "size": path.stat().st_size,
    }


def assess(report: dict[str, Any]) -> dict[str, Any]:
    checks = report.get("checks", {})
    windows = data_from_check(checks.get("windows"))
    recent_files = data_from_check(checks.get("recent_files"))
    screenshot = data_from_check(checks.get("screenshot"))

    candidate_count = len(report.get("candidate_windows", []))
    successful_dumps = [entry for entry in report.get("uia_dumps", []) if entry.get("dump", {}).get("ok")]
    named_controls = sum(
        len(entry.get("summary", {}).get("named_controls", []))
        for entry in successful_dumps
    )
    search_hits = sum(
        len(entry.get("summary", {}).get("search_hits", []))
        for entry in successful_dumps
    )

    black_ratio = None
    if isinstance(screenshot, dict):
        black_ratio = screenshot.get("black_ratio")

    findings = []
    if checks.get("health", {}).get("ok"):
        findings.append("agent_reachable")
    if isinstance(windows, list) and windows:
        findings.append("desktop_windows_visible")
    if candidate_count:
        findings.append("target_window_candidate_found")
    if successful_dumps:
        findings.append("uia_dump_succeeded")
    if named_controls:
        findings.append("uia_named_controls_visible")
    if search_hits:
        findings.append("uia_search_terms_found")
    if isinstance(recent_files, list) and recent_files:
        findings.append("recent_export_candidates_found")
    if isinstance(black_ratio, (int, float)) and black_ratio > 0.8:
        findings.append("screenshot_likely_blocked_or_blank")

    if successful_dumps and (named_controls or search_hits):
        viability = "promising"
    elif candidate_count:
        viability = "needs_manual_selector_check"
    elif checks.get("health", {}).get("ok"):
        viability = "agent_ok_target_not_seen"
    else:
        viability = "agent_unreachable"

    return {
        "viability": viability,
        "findings": findings,
        "candidate_window_count": candidate_count,
        "successful_uia_dump_count": len(successful_dumps),
        "named_control_sample_count": named_controls,
        "search_hit_count": search_hits,
        "screenshot_black_ratio": black_ratio,
    }


def render_markdown(report: dict[str, Any]) -> str:
    assessment = report.get("assessment", {})
    lines = [
        "# KAPA Field Recon Summary",
        "",
        f"- Captured at: `{report.get('captured_at')}`",
        f"- Base URL: `{report.get('base_url')}`",
        f"- Program: `{report.get('program')}`",
        f"- Backend: `{report.get('backend')}`",
        f"- Viability: `{assessment.get('viability')}`",
        "",
        "## Findings",
        "",
    ]
    for item in assessment.get("findings", []):
        lines.append(f"- {item}")
    if not assessment.get("findings"):
        lines.append("- none")

    lines.extend(["", "## Candidate Windows", ""])
    for window in report.get("candidate_windows", []):
        lines.append(
            "- "
            + f"handle=`{window.get('handle')}` "
            + f"title=`{window.get('title')}` "
            + f"process=`{window.get('process_name')}` "
            + f"reason=`{window.get('candidate_reason')}`"
        )
    if not report.get("candidate_windows"):
        lines.append("- none")

    lines.extend(["", "## UIA Dumps", ""])
    for entry in report.get("uia_dumps", []):
        dump = entry.get("dump", {})
        title = entry.get("window", {}).get("title")
        lines.append(f"- `{title}`: ok=`{dump.get('ok')}`")
        if not dump.get("ok"):
            lines.append(f"  error: `{dump.get('error')}`")
            continue
        summary = entry.get("summary", {})
        lines.append(
            "  "
            + f"nodes=`{summary.get('node_count')}`, "
            + f"depth=`{summary.get('max_depth_seen')}`, "
            + f"named_samples=`{len(summary.get('named_controls', []))}`, "
            + f"hits=`{len(summary.get('search_hits', []))}`"
        )
        dump_file = entry.get("dump_file")
        if dump_file:
            lines.append(f"  dump_file: `{dump_file}`")

    lines.extend(["", "## Next Decision", ""])
    lines.extend(next_decision_lines(assessment))
    lines.append("")
    return "\n".join(lines)


def next_decision_lines(assessment: dict[str, Any]) -> list[str]:
    viability = assessment.get("viability")
    if viability == "promising":
        return [
            "- Build the first recipe from stable UIA selectors or reliable hotkeys.",
            "- Prefer export files or clipboard table data for final extraction.",
        ]
    if viability == "needs_manual_selector_check":
        return [
            "- Run Accessibility Insights, FlaUInspect, or Inspect.exe on the target window.",
            "- Re-run this tool with more specific `--window-pattern` or `--search-term` values.",
        ]
    if viability == "agent_ok_target_not_seen":
        return [
            "- Launch KAPA HUB PLUS or KAIS in the same unlocked desktop session as the agent.",
            "- Confirm the agent is not running only as a Windows service.",
        ]
    return [
        "- Confirm the Windows Agent is running and reachable from the controller.",
        "- Check token, firewall, Tailscale, and bind host settings.",
    ]


def sanitize_filename(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)[:120] or "artifact.bin"


def shorten(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


if __name__ == "__main__":
    sys.exit(main())
