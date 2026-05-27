"""Remote update support: pull recipes and agent binaries from GitHub.

Design goals:
- No git dependency on the target PC — uses the GitHub HTTP API only.
- Outbound HTTPS to github.com / api.github.com only; no inbound, no server.
- Private repos supported via a read-only fine-grained PAT held locally.
- Every applied change is validated, atomic, and backed up so a bad recipe
  cannot brick the agent.

This module is import-safe on any OS (no Windows-only imports).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

from .config import GitHubConfig

KNOWN_ACTIONS = {
    "wait",
    "hotkey",
    "type_text",
    "click",
    "read_clipboard",
    "write_clipboard",
    "wait_until_clipboard_changes",
    "wait_until_window",
}

API_ROOT = "https://api.github.com"


class UpdateError(RuntimeError):
    pass


def validate_recipes(recipes: dict[str, Any]) -> list[str]:
    """Return a list of human-readable problems; empty list means valid."""
    problems: list[str] = []
    if not isinstance(recipes, dict):
        return ["recipes must be an object mapping name -> [steps]"]
    for name, steps in recipes.items():
        if not isinstance(steps, list):
            problems.append(f"{name}: steps must be a list")
            continue
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                problems.append(f"{name}[{i}]: step must be an object")
                continue
            action = step.get("action")
            if action not in KNOWN_ACTIONS:
                problems.append(
                    f"{name}[{i}]: unknown action {action!r} "
                    f"(known: {sorted(KNOWN_ACTIONS)})"
                )
    return problems


def atomic_write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def backup_recipes_dir(recipes_dir: Path) -> Path | None:
    """Snapshot the current recipes dir into recipes_dir/.backup/<ts>/."""
    if not recipes_dir.exists():
        return None
    ts = time.strftime("%Y%m%d-%H%M%S")
    backup_root = recipes_dir / ".backup" / ts
    backup_root.mkdir(parents=True, exist_ok=True)
    for path in recipes_dir.glob("*.json"):
        shutil.copy2(path, backup_root / path.name)
    return backup_root


def latest_backup(recipes_dir: Path) -> Path | None:
    backup_root = recipes_dir / ".backup"
    if not backup_root.exists():
        return None
    candidates = sorted((p for p in backup_root.iterdir() if p.is_dir()), reverse=True)
    return candidates[0] if candidates else None


def write_recipe_files(recipes_dir: Path, recipes: dict[str, list[dict[str, Any]]]) -> list[str]:
    """Persist each recipe as recipes_dir/<name>.json. Returns written names."""
    recipes_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for name, steps in recipes.items():
        doc = {"name": name, "steps": steps}
        atomic_write_json(recipes_dir / f"{name}.json", doc)
        written.append(name)
    return written


class GitHubUpdater:
    def __init__(self, gh: GitHubConfig, timeout: float = 30.0) -> None:
        self.gh = gh
        self.timeout = timeout

    def _headers(self, accept: str = "application/vnd.github+json") -> dict[str, str]:
        headers = {
            "Accept": accept,
            "User-Agent": "kapa-agent-updater",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.gh.token:
            headers["Authorization"] = f"Bearer {self.gh.token}"
        return headers

    def _get(self, url: str, accept: str = "application/vnd.github+json") -> bytes:
        req = urllib.request.Request(url, headers=self._headers(accept))
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:300]
            raise UpdateError(f"GitHub {exc.code} for {url}: {body}") from exc
        except urllib.error.URLError as exc:
            raise UpdateError(f"Network error for {url}: {exc.reason}") from exc

    # ----- recipes -----

    def fetch_recipes(self, ref: str | None = None) -> dict[str, list[dict[str, Any]]]:
        """Fetch all active recipes/*.json from the repo at a given ref."""
        ref = ref or self.gh.ref
        contents_url = (
            f"{API_ROOT}/repos/{self.gh.repo}/contents/recipes?ref={ref}"
        )
        listing = json.loads(self._get(contents_url))
        recipes: dict[str, list[dict[str, Any]]] = {}
        for item in listing:
            name = item.get("name", "")
            if not name.endswith(".json") or name.endswith(".template.json"):
                continue
            raw = self._get(item["download_url"], accept="application/vnd.github.raw")
            doc = json.loads(raw)
            if isinstance(doc, list):
                recipes[Path(name).stem] = doc
            elif isinstance(doc, dict):
                recipes[str(doc.get("name") or Path(name).stem)] = doc.get("steps", [])
        return recipes

    # ----- agent binary -----

    def latest_release(self) -> dict[str, Any]:
        url = f"{API_ROOT}/repos/{self.gh.repo}/releases/latest"
        return json.loads(self._get(url))

    def download_asset(self, dest: Path, asset_name: str | None = None) -> dict[str, Any]:
        """Download the named release asset to dest; returns asset metadata + sha256."""
        asset_name = asset_name or self.gh.asset_name
        release = self.latest_release()
        assets = {a["name"]: a for a in release.get("assets", [])}
        if asset_name not in assets:
            raise UpdateError(
                f"Asset {asset_name!r} not in release {release.get('tag_name')!r}; "
                f"have {list(assets)}"
            )
        asset = assets[asset_name]
        data = self._get(asset["url"], accept="application/octet-stream")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        sha = hashlib.sha256(data).hexdigest()
        # If a <asset>.sha256 asset exists, verify against it.
        expected = None
        sha_name = asset_name + ".sha256"
        if sha_name in assets:
            sha_blob = self._get(assets[sha_name]["url"], accept="application/octet-stream")
            expected = sha_blob.decode("utf-8", errors="replace").split()[0].strip()
        verified = expected is None or expected.lower() == sha.lower()
        return {
            "tag": release.get("tag_name"),
            "asset": asset_name,
            "size": len(data),
            "sha256": sha,
            "expected_sha256": expected,
            "verified": verified,
            "path": str(dest),
        }
