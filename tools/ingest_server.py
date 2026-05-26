#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import zipfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


class IngestState:
    def __init__(self, storage_dir: Path, token: str, max_bytes: int) -> None:
        self.storage_dir = storage_dir
        self.token = token
        self.max_bytes = max_bytes
        self.storage_dir.mkdir(parents=True, exist_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Receive KAPA capability-probe ZIP bundles.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Use a Tailscale IP for private remote ingest.")
    parser.add_argument("--port", type=int, default=8787, help="Bind port.")
    parser.add_argument("--storage-dir", default="runs", help="Directory to store uploaded runs.")
    parser.add_argument("--token", default="", help="Optional bearer token required for uploads.")
    parser.add_argument("--max-mb", type=int, default=50, help="Maximum upload size in MB.")
    args = parser.parse_args()

    state = IngestState(Path(args.storage_dir), args.token, args.max_mb * 1024 * 1024)

    class Handler(IngestHandler):
        ingest_state = state

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Listening on http://{args.host}:{args.port}")
    print(f"Storing runs in {state.storage_dir.resolve()}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping ingest server")
    finally:
        server.server_close()
    return 0


class IngestHandler(BaseHTTPRequestHandler):
    ingest_state: IngestState

    server_version = "KapaIngest/0.1"

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path == "/health":
            self.write_json(HTTPStatus.OK, {"ok": True})
            return
        if self.path == "/runs":
            self.write_json(HTTPStatus.OK, {"runs": list_runs(self.ingest_state.storage_dir)})
            return
        self.write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path != "/runs":
            self.write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})
            return
        if not self.authorized():
            self.write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
            return

        content_length = self.headers.get("Content-Length")
        if not content_length:
            self.write_json(HTTPStatus.LENGTH_REQUIRED, {"ok": False, "error": "content_length_required"})
            return
        try:
            size = int(content_length)
        except ValueError:
            self.write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid_content_length"})
            return
        if size > self.ingest_state.max_bytes:
            self.write_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"ok": False, "error": "upload_too_large"})
            return

        body = self.rfile.read(size)
        if not looks_like_zip(body):
            self.write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "expected_zip_body"})
            return

        bundle_name = sanitize_name(self.headers.get("X-Kapa-Bundle-Name", "bundle.zip"))
        run_id = make_run_id(bundle_name)
        run_dir = self.ingest_state.storage_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        zip_path = run_dir / bundle_name
        zip_path.write_bytes(body)

        extract_dir = run_dir / "extracted"
        extract_dir.mkdir()
        extract_summary = safe_extract_zip(zip_path, extract_dir)

        metadata = {
            "ok": True,
            "run_id": run_id,
            "received_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "bundle_name": bundle_name,
            "bundle_size": len(body),
            "bundle_path": str(zip_path),
            "extract_dir": str(extract_dir),
            "extract_summary": extract_summary,
            "client": {
                "address": self.client_address[0],
                "user_agent": self.headers.get("User-Agent"),
            },
        }
        metadata.update(read_probe_summary(extract_dir))
        (run_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

        self.write_json(HTTPStatus.CREATED, metadata)

    def authorized(self) -> bool:
        token = self.ingest_state.token
        if not token:
            return True
        expected = f"Bearer {token}"
        return self.headers.get("Authorization") == expected

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - BaseHTTPRequestHandler API
        sys.stderr.write("%s - - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), format % args))

    def write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def list_runs(storage_dir: Path) -> list[dict[str, Any]]:
    runs = []
    for path in sorted(storage_dir.iterdir(), reverse=True):
        metadata_path = path / "metadata.json"
        if not metadata_path.exists():
            continue
        try:
            runs.append(json.loads(metadata_path.read_text(encoding="utf-8")))
        except Exception:
            runs.append({"run_id": path.name, "metadata_error": True})
    return runs


def looks_like_zip(body: bytes) -> bool:
    return body.startswith(b"PK\x03\x04") or body.startswith(b"PK\x05\x06") or body.startswith(b"PK\x07\x08")


def make_run_id(bundle_name: str) -> str:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    stem = sanitize_name(Path(bundle_name).stem)
    return f"{timestamp}-{stem}"[:120]


def sanitize_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned[:100] or "bundle.zip"


def safe_extract_zip(zip_path: Path, extract_dir: Path) -> dict[str, Any]:
    extracted = []
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            member_path = Path(member.filename)
            if member.is_dir():
                continue
            if member_path.is_absolute() or ".." in member_path.parts:
                extracted.append({"name": member.filename, "skipped": True, "reason": "unsafe_path"})
                continue
            target = extract_dir / member_path
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source:
                target.write_bytes(source.read())
            extracted.append({"name": member.filename, "size": target.stat().st_size})
    return {"file_count": len([item for item in extracted if not item.get("skipped")]), "files": extracted}


def read_probe_summary(extract_dir: Path) -> dict[str, Any]:
    report_path = extract_dir / "capability-report.json"
    summary_path = extract_dir / "capability-summary.md"
    result: dict[str, Any] = {}
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            result["probe"] = {
                "captured_at": report.get("captured_at"),
                "host": report.get("host", {}),
                "assessment": report.get("assessment", {}),
            }
        except Exception as exc:  # noqa: BLE001 - metadata should tolerate bad uploads
            result["probe_error"] = str(exc)
    if summary_path.exists():
        result["summary_path"] = str(summary_path)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
