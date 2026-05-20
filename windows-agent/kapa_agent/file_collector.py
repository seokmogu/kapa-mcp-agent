from __future__ import annotations

import shutil
import time
from pathlib import Path

from .models import ArtifactInfo
from .storage import ArtifactStore


def default_export_folders() -> list[Path]:
    home = Path.home()
    candidates = [
        home / "Downloads",
        home / "Documents",
        home / "Desktop",
    ]
    return [path for path in candidates if path.exists()]


def recent_files(
    folders: list[str],
    patterns: list[str],
    minutes: int,
    limit: int,
) -> list[Path]:
    roots = [Path(folder).expanduser() for folder in folders] if folders else default_export_folders()
    cutoff = time.time() - minutes * 60
    found: list[Path] = []
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        for pattern in patterns:
            found.extend(
                path
                for path in root.glob(pattern)
                if path.is_file() and path.stat().st_mtime >= cutoff
            )
    return sorted(found, key=lambda path: path.stat().st_mtime, reverse=True)[:limit]


def info_for_path(path: Path) -> ArtifactInfo:
    stat = path.stat()
    return ArtifactInfo(
        id="external",
        name=path.name,
        path=str(path),
        size=stat.st_size,
        modified_at=stat.st_mtime,
    )


def collect_recent_files(
    artifact_store: ArtifactStore,
    folders: list[str],
    patterns: list[str],
    minutes: int,
    limit: int,
) -> list[ArtifactInfo]:
    collected: list[ArtifactInfo] = []
    for path in recent_files(folders, patterns, minutes, limit):
        target = artifact_store.reserve_path(path.name)
        shutil.copy2(path, target)
        collected.append(artifact_store.info(target))
    return collected

