from __future__ import annotations

import time
import uuid
from pathlib import Path

from .models import ArtifactInfo


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save_text(self, name: str, content: str) -> ArtifactInfo:
        artifact_id = uuid.uuid4().hex
        safe_name = self._safe_name(name)
        path = self.root / f"{artifact_id}_{safe_name}"
        path.write_text(content, encoding="utf-8")
        return self._info(path)

    def save_bytes(self, name: str, content: bytes) -> ArtifactInfo:
        artifact_id = uuid.uuid4().hex
        safe_name = self._safe_name(name)
        path = self.root / f"{artifact_id}_{safe_name}"
        path.write_bytes(content)
        return self._info(path)

    def reserve_path(self, name: str) -> Path:
        artifact_id = uuid.uuid4().hex
        safe_name = self._safe_name(name)
        return self.root / f"{artifact_id}_{safe_name}"

    def info(self, path: Path) -> ArtifactInfo:
        return self._info(path)

    def list(self) -> list[ArtifactInfo]:
        return sorted(
            [self._info(path) for path in self.root.glob("*") if path.is_file()],
            key=lambda item: item.modified_at,
            reverse=True,
        )

    def path_for_id(self, artifact_id: str) -> Path | None:
        for path in self.root.glob(f"{artifact_id}_*"):
            if path.is_file():
                return path
        return None

    def _info(self, path: Path) -> ArtifactInfo:
        stat = path.stat()
        artifact_id = path.name.split("_", 1)[0]
        return ArtifactInfo(
            id=artifact_id,
            name=path.name,
            path=str(path),
            size=stat.st_size,
            modified_at=stat.st_mtime,
        )

    @staticmethod
    def _safe_name(name: str) -> str:
        cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in name)
        return cleaned.strip("._") or f"artifact_{int(time.time())}.txt"
