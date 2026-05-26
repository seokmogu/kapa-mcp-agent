from __future__ import annotations

import argparse
import base64
import ctypes
import hashlib
import json
import os
import platform
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile
from collections import Counter
from ctypes import wintypes
from pathlib import Path
from typing import Any

from .screen_capture import estimate_black_ratio


DEFAULT_WINDOW_PATTERN = r"(KAPA|HUB|KAIS)"
DEFAULT_TERMS = [
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
EXPORT_PATTERNS = ["*.xlsx", "*.xls", "*.csv", "*.pdf", "*.hwp", "*.hwpx", "*.txt"]


def load_probe_config(argv: list[str]) -> dict[str, Any]:
    explicit_path = ""
    for index, value in enumerate(argv):
        if value == "--config" and index + 1 < len(argv):
            explicit_path = argv[index + 1]
            break
        if value.startswith("--config="):
            explicit_path = value.split("=", 1)[1]
            break

    candidates = []
    if explicit_path:
        candidates.append(Path(explicit_path))
    else:
        candidates.extend(default_config_paths())

    for path in candidates:
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8-sig"))
                if isinstance(data, dict):
                    data["_config_path"] = str(path)
                    return data
        except Exception:
            return {"_config_path": str(path), "_config_error": "failed_to_read"}
    return {}


def default_config_paths() -> list[Path]:
    paths = [Path.cwd() / "probe.config.json"]
    bundle_root = getattr(sys, "_MEIPASS", "")
    if bundle_root:
        paths.append(Path(bundle_root) / "probe.config.json")
    executable_dir = Path(sys.executable).resolve().parent
    paths.append(executable_dir / "probe.config.json")
    script_dir = Path(__file__).resolve().parent
    paths.append(script_dir.parent / "probe.config.json")
    deduped = []
    seen = set()
    for path in paths:
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return deduped


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    config_defaults = load_probe_config(raw_argv)
    parser = argparse.ArgumentParser(
        description="Probe local Windows automation/capture options for KAPA/KAIS field validation."
    )
    parser.add_argument(
        "--config",
        default=config_defaults.get("_config_path", ""),
        help="Optional probe config JSON. Defaults to probe.config.json next to the EXE or in cwd.",
    )
    parser.add_argument("--out-dir", default=config_defaults.get("out_dir", ""), help="Output directory. Defaults to kapa-capability-probe-<ts>.")
    parser.add_argument("--window-pattern", default=config_defaults.get("window_pattern", DEFAULT_WINDOW_PATTERN), help="Candidate window regex.")
    parser.add_argument("--term", action="append", default=config_defaults.get("terms", []), help="UIA search term. May be repeated.")
    parser.add_argument("--max-depth", type=int, default=int(config_defaults.get("max_depth", 6)), help="Maximum UIA tree depth per candidate.")
    parser.add_argument("--max-nodes", type=int, default=int(config_defaults.get("max_nodes", 1000)), help="Maximum UIA nodes per candidate.")
    parser.add_argument("--recent-minutes", type=int, default=int(config_defaults.get("recent_minutes", 240)), help="Recent export-file lookback window.")
    parser.add_argument("--include-clipboard-text", action="store_true", default=bool(config_defaults.get("include_clipboard_text", False)), help="Include raw clipboard text.")
    parser.add_argument("--include-screenshot-files", action="store_true", default=bool(config_defaults.get("include_screenshot_files", False)), help="Keep screenshot PNG files in bundle.")
    parser.add_argument(
        "--push-url",
        default=config_defaults.get("push_url", os.getenv("KAPA_PROBE_PUSH_URL", "")),
        help="Optional URL to POST the generated zip bundle to. Defaults to KAPA_PROBE_PUSH_URL.",
    )
    parser.add_argument(
        "--push-token",
        default=config_defaults.get("push_token", os.getenv("KAPA_PROBE_PUSH_TOKEN", "")),
        help="Optional bearer token for --push-url. Defaults to KAPA_PROBE_PUSH_TOKEN.",
    )
    parser.add_argument(
        "--push-format",
        default=config_defaults.get("push_format", os.getenv("KAPA_PROBE_PUSH_FORMAT", "raw-zip")),
        choices=["raw-zip", "json-base64"],
        help="Upload body format. Use json-base64 for Google Apps Script style endpoints.",
    )
    args = parser.parse_args(raw_argv)

    captured_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    out_dir = Path(args.out_dir) if args.out_dir else default_output_root() / f"kapa-capability-probe-{int(time.time())}"
    out_dir.mkdir(parents=True, exist_ok=True)
    screenshot_dir = out_dir / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    terms = args.term or DEFAULT_TERMS
    report: dict[str, Any] = {
        "captured_at": captured_at,
        "host": host_info(),
        "options": {
            "config": args.config,
            "window_pattern": args.window_pattern,
            "terms": terms,
            "max_depth": args.max_depth,
            "max_nodes": args.max_nodes,
            "recent_minutes": args.recent_minutes,
            "include_clipboard_text": args.include_clipboard_text,
            "include_screenshot_files": args.include_screenshot_files,
            "push_configured": bool(args.push_url),
            "push_format": args.push_format,
        },
        "dependencies": dependency_report(),
        "windows": {},
        "candidate_windows": [],
        "capture_methods": [],
        "clipboard": {},
        "recent_files": [],
        "uia_dumps": [],
        "assessment": {},
    }

    report["windows"] = collect_windows(args.window_pattern)
    report["candidate_windows"] = select_candidates(report["windows"], args.window_pattern)
    report["capture_methods"] = run_capture_probes(screenshot_dir, report["candidate_windows"])
    report["clipboard"] = clipboard_report(args.include_clipboard_text)
    report["recent_files"] = recent_file_report(args.recent_minutes)
    report["uia_dumps"] = run_uia_probes(
        report["candidate_windows"],
        out_dir,
        args.max_depth,
        args.max_nodes,
        terms,
    )
    report["assessment"] = assess(report)

    remove_screenshot_files = not args.include_screenshot_files
    if remove_screenshot_files:
        for item in report["capture_methods"]:
            path = item.get("path")
            if path:
                Path(path).unlink(missing_ok=True)
                item["path_removed_from_bundle"] = True
                item.pop("path", None)

    json_path = out_dir / "capability-report.json"
    markdown_path = out_dir / "capability-summary.md"
    zip_path = out_dir.with_suffix(".zip")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    make_zip(out_dir, zip_path)

    push_result = None
    if args.push_url:
        push_result = push_bundle(args.push_url, args.push_token, zip_path, args.push_format, report)
        push_path = out_dir / "push-result.json"
        push_path.write_text(json.dumps(push_result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json_path)
    print(markdown_path)
    print(zip_path)
    if push_result:
        print(json.dumps(push_result, ensure_ascii=False))
    write_last_run_note(out_dir, json_path, markdown_path, zip_path, push_result)
    show_completion_message(zip_path, push_result)
    return 0


def default_output_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "runs"
    return Path.cwd()


def write_last_run_note(
    out_dir: Path,
    json_path: Path,
    markdown_path: Path,
    zip_path: Path,
    push_result: dict[str, Any] | None,
) -> None:
    lines = [
        f"finished_at={time.strftime('%Y-%m-%dT%H:%M:%S%z')}",
        f"out_dir={out_dir}",
        f"json={json_path}",
        f"summary={markdown_path}",
        f"zip={zip_path}",
    ]
    if push_result is not None:
        lines.append(f"push_ok={push_result.get('ok')}")
        lines.append(f"push_status={push_result.get('status', '')}")
        lines.append(f"push_error={push_result.get('error', '')}")
    try:
        note_path = default_output_root() / "kapa-probe-last-run.txt"
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass


def show_completion_message(zip_path: Path, push_result: dict[str, Any] | None) -> None:
    if not getattr(sys, "frozen", False) or not is_windows():
        return
    if push_result is None:
        message = f"진단 완료\n\n결과 파일:\n{zip_path}"
    elif push_result.get("ok"):
        message = "진단 완료\n\n결과가 서버로 전송되었습니다."
    else:
        message = (
            "진단 완료, 서버 전송 실패\n\n"
            f"결과 파일:\n{zip_path}\n\n"
            f"오류:\n{push_result.get('error', push_result.get('status', 'unknown'))}"
        )
    try:
        ctypes.windll.user32.MessageBoxW(None, message, "KAPA Probe", 0x40)
    except Exception:
        pass


def host_info() -> dict[str, Any]:
    return {
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "user": os.getenv("USERNAME") or os.getenv("USER"),
        "computername": os.getenv("COMPUTERNAME"),
        "sessionname": os.getenv("SESSIONNAME"),
        "cwd": str(Path.cwd()),
        "python": sys.version,
        "is_windows": is_windows(),
        "is_interactive_session": bool(os.getenv("SESSIONNAME")),
        "is_elevated": is_elevated(),
    }


def dependency_report() -> dict[str, Any]:
    modules = {}
    for name in ["pywinauto", "pyperclip", "mss", "PIL", "psutil", "win32gui", "win32ui", "win32con"]:
        modules[name] = module_available(name)
    return modules


def module_available(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


def collect_windows(window_pattern: str) -> dict[str, Any]:
    return {
        "ctypes": collect_windows_ctypes(),
        "pywinauto_uia": collect_windows_pywinauto("uia"),
        "pywinauto_win32": collect_windows_pywinauto("win32"),
        "pattern": window_pattern,
    }


def collect_windows_ctypes() -> dict[str, Any]:
    if not is_windows():
        return {"ok": False, "error": "not_windows"}
    try:
        user32 = ctypes.windll.user32
        windows: list[dict[str, Any]] = []

        enum_windows_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def callback(hwnd: int, _lparam: int) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return True
            title = get_window_text(hwnd)
            if not title:
                return True
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            windows.append(
                {
                    "handle": hwnd,
                    "title": title,
                    "class_name": get_class_name(hwnd),
                    "process_id": int(pid.value) if pid.value else None,
                    "visible": True,
                }
            )
            return True

        user32.EnumWindows(enum_windows_proc(callback), 0)
        return {"ok": True, "windows": windows}
    except Exception as exc:  # noqa: BLE001 - diagnostic report should keep errors
        return {"ok": False, "error": str(exc)}


def collect_windows_pywinauto(backend: str) -> dict[str, Any]:
    if not is_windows():
        return {"ok": False, "error": "not_windows"}
    try:
        from pywinauto import Desktop

        windows = []
        for win in Desktop(backend=backend).windows():
            info = win.element_info
            windows.append(
                {
                    "handle": getattr(info, "handle", None),
                    "title": win.window_text(),
                    "class_name": getattr(info, "class_name", None),
                    "process_id": getattr(info, "process_id", None),
                    "process_name": process_name(getattr(info, "process_id", None)),
                    "visible": win.is_visible(),
                    "backend": backend,
                }
            )
        return {"ok": True, "windows": windows}
    except Exception as exc:  # noqa: BLE001 - diagnostic report should keep errors
        return {"ok": False, "error": str(exc)}


def get_window_text(hwnd: int) -> str:
    user32 = ctypes.windll.user32
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def get_class_name(hwnd: int) -> str:
    user32 = ctypes.windll.user32
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, 256)
    return buffer.value


def select_candidates(windows_report: dict[str, Any], window_pattern: str) -> list[dict[str, Any]]:
    regex = re.compile(window_pattern, re.IGNORECASE)
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[Any, str]] = set()
    for source, result in windows_report.items():
        if source == "pattern" or not isinstance(result, dict) or not result.get("ok"):
            continue
        for item in result.get("windows", []):
            if is_self_window(item):
                continue
            title = str(item.get("title", ""))
            proc = str(item.get("process_name", ""))
            class_name = str(item.get("class_name", ""))
            if not (regex.search(title) or regex.search(proc) or regex.search(class_name)):
                continue
            key = (item.get("handle"), title)
            if key in seen:
                continue
            seen.add(key)
            candidate = dict(item)
            candidate["candidate_source"] = source
            candidates.append(candidate)
    return candidates


def is_self_window(item: dict[str, Any]) -> bool:
    process_id = item.get("process_id")
    process_name = str(item.get("process_name") or "").lower()
    title = str(item.get("title") or "").lower()
    class_name = str(item.get("class_name") or "").lower()
    if process_id == os.getpid():
        return True
    if process_name == "kapa-probe.exe":
        return True
    if "kapa-probe.exe" in title:
        return True
    if class_name == "pyinstalleronefilehiddenwindow":
        return True
    return False


def run_capture_probes(screenshot_dir: Path, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    probes = [
        capture_with_mss(screenshot_dir),
        capture_with_pillow(screenshot_dir),
        capture_with_gdi_desktop(screenshot_dir),
    ]
    for index, candidate in enumerate(candidates[:4]):
        probes.append(capture_with_printwindow(screenshot_dir, candidate, index + 1))
    return probes


def capture_with_mss(screenshot_dir: Path) -> dict[str, Any]:
    method = "mss_monitor_1"
    try:
        import mss
        import mss.tools

        with mss.mss() as screen:
            if len(screen.monitors) < 2:
                return {"method": method, "ok": False, "error": "monitor_1_not_available"}
            shot = screen.grab(screen.monitors[1])
            png = mss.tools.to_png(shot.rgb, shot.size)
        path = screenshot_dir / f"{method}.png"
        path.write_bytes(png)
        return capture_result(method, True, path, shot.width, shot.height, shot.rgb)
    except Exception as exc:  # noqa: BLE001 - diagnostic report should keep errors
        return {"method": method, "ok": False, "error": str(exc)}


def capture_with_pillow(screenshot_dir: Path) -> dict[str, Any]:
    method = "pillow_imagegrab"
    try:
        from PIL import ImageGrab

        image = ImageGrab.grab(all_screens=True)
        path = screenshot_dir / f"{method}.png"
        image.save(path)
        rgb = image.convert("RGB").tobytes()
        return capture_result(method, True, path, image.width, image.height, rgb)
    except Exception as exc:  # noqa: BLE001 - diagnostic report should keep errors
        return {"method": method, "ok": False, "error": str(exc)}


def capture_with_gdi_desktop(screenshot_dir: Path) -> dict[str, Any]:
    method = "pywin32_gdi_desktop"
    try:
        import win32con
        import win32gui
        import win32ui
        from PIL import Image

        hwnd = win32gui.GetDesktopWindow()
        width = win32api_metric(0)
        height = win32api_metric(1)
        hwnd_dc = win32gui.GetWindowDC(hwnd)
        src_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        mem_dc = src_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(src_dc, width, height)
        mem_dc.SelectObject(bitmap)
        mem_dc.BitBlt((0, 0), (width, height), src_dc, (0, 0), win32con.SRCCOPY)

        bmp_info = bitmap.GetInfo()
        bmp_bits = bitmap.GetBitmapBits(True)
        image = Image.frombuffer(
            "RGB",
            (bmp_info["bmWidth"], bmp_info["bmHeight"]),
            bmp_bits,
            "raw",
            "BGRX",
            0,
            1,
        )
        path = screenshot_dir / f"{method}.png"
        image.save(path)
        rgb = image.convert("RGB").tobytes()
        win32gui.DeleteObject(bitmap.GetHandle())
        mem_dc.DeleteDC()
        src_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)
        return capture_result(method, True, path, image.width, image.height, rgb)
    except Exception as exc:  # noqa: BLE001 - diagnostic report should keep errors
        return {"method": method, "ok": False, "error": str(exc)}


def capture_with_printwindow(screenshot_dir: Path, candidate: dict[str, Any], index: int) -> dict[str, Any]:
    method = f"pywin32_printwindow_{index}"
    handle = candidate.get("handle")
    if not isinstance(handle, int) or handle <= 0:
        return {"method": method, "ok": False, "error": "candidate_has_no_handle", "candidate": candidate}
    try:
        import win32con
        import win32gui
        import win32ui
        from PIL import Image

        left, top, right, bottom = win32gui.GetWindowRect(handle)
        width = max(1, right - left)
        height = max(1, bottom - top)
        hwnd_dc = win32gui.GetWindowDC(handle)
        src_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        mem_dc = src_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(src_dc, width, height)
        mem_dc.SelectObject(bitmap)
        print_window_ok = bool(ctypes.windll.user32.PrintWindow(handle, mem_dc.GetSafeHdc(), 0x2))
        if not print_window_ok:
            mem_dc.BitBlt((0, 0), (width, height), src_dc, (0, 0), win32con.SRCCOPY)

        bmp_info = bitmap.GetInfo()
        bmp_bits = bitmap.GetBitmapBits(True)
        image = Image.frombuffer(
            "RGB",
            (bmp_info["bmWidth"], bmp_info["bmHeight"]),
            bmp_bits,
            "raw",
            "BGRX",
            0,
            1,
        )
        path = screenshot_dir / f"{method}.png"
        image.save(path)
        rgb = image.convert("RGB").tobytes()
        win32gui.DeleteObject(bitmap.GetHandle())
        mem_dc.DeleteDC()
        src_dc.DeleteDC()
        win32gui.ReleaseDC(handle, hwnd_dc)
        result = capture_result(method, True, path, image.width, image.height, rgb)
        result["print_window_ok"] = print_window_ok
        result["candidate"] = {
            "handle": candidate.get("handle"),
            "title": candidate.get("title"),
            "process_name": candidate.get("process_name"),
        }
        return result
    except Exception as exc:  # noqa: BLE001 - diagnostic report should keep errors
        return {"method": method, "ok": False, "error": str(exc), "candidate": candidate}


def win32api_metric(index: int) -> int:
    user32 = ctypes.windll.user32
    return int(user32.GetSystemMetrics(index))


def capture_result(
    method: str,
    ok: bool,
    path: Path,
    width: int,
    height: int,
    rgb: bytes,
) -> dict[str, Any]:
    return {
        "method": method,
        "ok": ok,
        "path": str(path),
        "width": width,
        "height": height,
        "black_ratio": estimate_black_ratio(rgb),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "size": path.stat().st_size,
    }


def clipboard_report(include_text: bool) -> dict[str, Any]:
    try:
        import pyperclip

        text = pyperclip.paste()
        report = {
            "ok": True,
            "length": len(text),
            "sha256": hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest(),
            "contains_text": bool(text),
        }
        if include_text:
            report["text"] = text
        return report
    except Exception as exc:  # noqa: BLE001 - diagnostic report should keep errors
        return {"ok": False, "error": str(exc)}


def recent_file_report(minutes: int) -> list[dict[str, Any]]:
    now = time.time()
    cutoff = now - minutes * 60
    folders = [
        Path.home() / "Downloads",
        Path.home() / "Documents",
        Path.home() / "Desktop",
    ]
    found: list[dict[str, Any]] = []
    for folder in folders:
        if not folder.exists():
            continue
        for pattern in EXPORT_PATTERNS:
            for path in folder.glob(pattern):
                try:
                    stat = path.stat()
                except OSError:
                    continue
                if stat.st_mtime < cutoff:
                    continue
                found.append(
                    {
                        "path": str(path),
                        "name": path.name,
                        "size": stat.st_size,
                        "modified_at": stat.st_mtime,
                        "modified_age_minutes": round((now - stat.st_mtime) / 60, 2),
                    }
                )
    return sorted(found, key=lambda item: item["modified_at"], reverse=True)[:100]


def run_uia_probes(
    candidates: list[dict[str, Any]],
    out_dir: Path,
    max_depth: int,
    max_nodes: int,
    terms: list[str],
) -> list[dict[str, Any]]:
    if not is_windows():
        return [{"ok": False, "error": "not_windows"}]
    results = []
    for index, candidate in enumerate(candidates[:8]):
        selector = selector_for_candidate(candidate)
        try:
            tree = dump_uia_tree(selector, max_depth, max_nodes)
            dump_path = out_dir / f"uia-dump-{index + 1}.json"
            dump_path.write_text(json.dumps(tree, ensure_ascii=False, indent=2), encoding="utf-8")
            results.append(
                {
                    "ok": True,
                    "candidate": candidate,
                    "selector": selector,
                    "summary": summarize_uia_tree(tree, terms),
                    "dump_file": str(dump_path),
                }
            )
        except Exception as exc:  # noqa: BLE001 - diagnostic report should keep errors
            results.append(
                {
                    "ok": False,
                    "candidate": candidate,
                    "selector": selector,
                    "error": str(exc),
                }
            )
    return results


def selector_for_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    handle = candidate.get("handle")
    if isinstance(handle, int) and handle > 0:
        return {"handle": handle, "backend": "uia"}
    return {"title_re": re.escape(str(candidate.get("title", ""))), "backend": "uia"}


def dump_uia_tree(selector: dict[str, Any], max_depth: int, max_nodes: int) -> dict[str, Any]:
    from .models import WindowSelector
    from .windows_automation import WindowsAutomation

    automation = WindowsAutomation()
    return automation.dump_tree(WindowSelector(**selector), max_depth, max_nodes)


def summarize_uia_tree(tree: Any, terms: list[str]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "node_count": 0,
        "max_depth_seen": 0,
        "control_types": {},
        "named_controls": [],
        "search_hits": [],
    }
    control_types: Counter[str] = Counter()

    def walk(node: Any, depth: int, path: str) -> None:
        if not isinstance(node, dict):
            return
        summary["node_count"] += 1
        summary["max_depth_seen"] = max(summary["max_depth_seen"], depth)
        name = str(node.get("name") or "")
        control_type = str(node.get("control_type") or "")
        automation_id = str(node.get("automation_id") or "")
        class_name = str(node.get("class_name") or "")
        if control_type:
            control_types[control_type] += 1
        if name or automation_id:
            summary["named_controls"].append(
                {
                    "path": path,
                    "name": name,
                    "control_type": control_type,
                    "automation_id": automation_id,
                    "class_name": class_name,
                    "rectangle": node.get("rectangle"),
                }
            )
        text = " ".join([name, control_type, automation_id, class_name]).lower()
        for term in terms:
            if term.lower() in text:
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
            walk(child, depth + 1, f"{path}/{child_index}:{shorten(child_name, 40)}")

    walk(tree, 0, "root")
    summary["control_types"] = dict(control_types.most_common())
    summary["named_controls"] = summary["named_controls"][:150]
    summary["search_hits"] = summary["search_hits"][:200]
    return summary


def assess(report: dict[str, Any]) -> dict[str, Any]:
    candidates = report.get("candidate_windows", [])
    captures = report.get("capture_methods", [])
    uia = report.get("uia_dumps", [])
    recent_files = report.get("recent_files", [])

    capture_ok = [item for item in captures if item.get("ok")]
    nonblack_capture = [
        item for item in capture_ok
        if isinstance(item.get("black_ratio"), (int, float)) and item["black_ratio"] < 0.8
    ]
    successful_uia = [item for item in uia if item.get("ok")]
    search_hits = sum(len(item.get("summary", {}).get("search_hits", [])) for item in successful_uia)
    named_controls = sum(len(item.get("summary", {}).get("named_controls", [])) for item in successful_uia)

    options = []
    if nonblack_capture:
        options.append("screen_capture")
    if successful_uia and named_controls:
        options.append("uia")
    if report.get("clipboard", {}).get("ok"):
        options.append("clipboard")
    if recent_files:
        options.append("export_file_collection")

    if "uia" in options or "export_file_collection" in options:
        viability = "promising"
    elif candidates:
        viability = "target_seen_needs_manual_probe"
    elif capture_ok:
        viability = "capture_only_target_not_identified"
    else:
        viability = "blocked_or_missing_dependencies"

    return {
        "viability": viability,
        "implementation_options": options,
        "candidate_window_count": len(candidates),
        "capture_ok_count": len(capture_ok),
        "nonblack_capture_count": len(nonblack_capture),
        "successful_uia_dump_count": len(successful_uia),
        "uia_named_control_count": named_controls,
        "uia_search_hit_count": search_hits,
        "recent_file_count": len(recent_files),
    }


def render_markdown(report: dict[str, Any]) -> str:
    assessment = report.get("assessment", {})
    lines = [
        "# KAPA Capability Probe Summary",
        "",
        f"- Captured at: `{report.get('captured_at')}`",
        f"- Computer: `{report.get('host', {}).get('computername')}`",
        f"- User/session: `{report.get('host', {}).get('user')}` / `{report.get('host', {}).get('sessionname')}`",
        f"- Elevated: `{report.get('host', {}).get('is_elevated')}`",
        f"- Viability: `{assessment.get('viability')}`",
        f"- Options: `{', '.join(assessment.get('implementation_options', [])) or 'none'}`",
        "",
        "## Capture Methods",
        "",
    ]
    for item in report.get("capture_methods", []):
        lines.append(
            "- "
            + f"{item.get('method')}: ok=`{item.get('ok')}`, "
            + f"black_ratio=`{item.get('black_ratio')}`, "
            + f"error=`{item.get('error', '')}`"
        )

    lines.extend(["", "## Candidate Windows", ""])
    for item in report.get("candidate_windows", []):
        lines.append(
            "- "
            + f"handle=`{item.get('handle')}` "
            + f"title=`{item.get('title')}` "
            + f"process=`{item.get('process_name')}` "
            + f"source=`{item.get('candidate_source')}`"
        )
    if not report.get("candidate_windows"):
        lines.append("- none")

    lines.extend(["", "## UIA", ""])
    for item in report.get("uia_dumps", []):
        title = item.get("candidate", {}).get("title")
        if not item.get("ok"):
            lines.append(f"- `{title}`: failed `{item.get('error')}`")
            continue
        summary = item.get("summary", {})
        lines.append(
            "- "
            + f"`{title}`: nodes=`{summary.get('node_count')}`, "
            + f"named=`{len(summary.get('named_controls', []))}`, "
            + f"hits=`{len(summary.get('search_hits', []))}`"
        )

    lines.extend(["", "## Recent Export Candidates", ""])
    for item in report.get("recent_files", [])[:20]:
        lines.append(f"- `{item.get('path')}` size=`{item.get('size')}` age_min=`{item.get('modified_age_minutes')}`")
    if not report.get("recent_files"):
        lines.append("- none")

    lines.extend(["", "## Next Step", ""])
    lines.extend(next_step_lines(assessment))
    lines.append("")
    return "\n".join(lines)


def next_step_lines(assessment: dict[str, Any]) -> list[str]:
    options = set(assessment.get("implementation_options", []))
    if "uia" in options:
        return [
            "- Build the first recipe from the saved UIA dumps.",
            "- Use capture only as a diagnostic channel unless black_ratio is consistently low.",
        ]
    if "export_file_collection" in options:
        return [
            "- Prefer automating export commands and collecting files from known folders.",
            "- Run another probe immediately after a manual export to identify the exact output path.",
        ]
    if "screen_capture" in options:
        return [
            "- Screen capture works, but still test UIA and export paths for more reliable automation.",
        ]
    return [
        "- Confirm KAPA/KAIS is open in the same unlocked desktop session.",
        "- Install the optional probe dependencies and rerun before considering hardware KVM.",
    ]


def make_zip(source_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in source_dir.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(source_dir))


def push_bundle(
    push_url: str,
    token: str,
    zip_path: Path,
    push_format: str,
    report: dict[str, Any],
) -> dict[str, Any]:
    headers = {"X-Kapa-Bundle-Name": zip_path.name}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    if push_format == "json-base64":
        body = json.dumps(
            {
                "filename": zip_path.name,
                "content_type": "application/zip",
                "token": token,
                "captured_at": report.get("captured_at"),
                "host": report.get("host", {}),
                "assessment": report.get("assessment", {}),
                "bundle_base64": base64.b64encode(zip_path.read_bytes()).decode("ascii"),
            },
            ensure_ascii=False,
        ).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    else:
        body = zip_path.read_bytes()
        headers["Content-Type"] = "application/zip"

    request = urllib.request.Request(push_url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read().decode("utf-8", errors="replace")
            return {"ok": True, "status": response.status, "response": payload}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code, "error": exc.read().decode("utf-8", errors="replace")}
    except Exception as exc:  # noqa: BLE001 - push is optional
        return {"ok": False, "error": str(exc)}


def process_name(process_id: int | None) -> str | None:
    if process_id is None:
        return None
    try:
        import psutil

        return psutil.Process(process_id).name()
    except Exception:
        return None


def is_windows() -> bool:
    return platform.system().lower() == "windows"


def is_elevated() -> bool | None:
    if not is_windows():
        return None
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return None


def shorten(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


if __name__ == "__main__":
    raise SystemExit(main())
