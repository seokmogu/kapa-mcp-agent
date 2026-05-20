from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class AgentConfig:
    bind_host: str = "127.0.0.1"
    port: int = 8765
    artifact_dir: Path = Path("artifacts")
    log_dir: Path = Path("logs")
    auth_token: str | None = None
    recipes: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    default_window_patterns: dict[str, str] = field(
        default_factory=lambda: {
            "kapa_hub_plus": r".*(KAPA\s*HUB|KAPA-HUB).*",
            "kais": r".*(부동산통합업무시스템|KAIS).*",
        }
    )

    @classmethod
    def load(cls) -> "AgentConfig":
        config_path = Path(os.getenv("KAPA_AGENT_CONFIG", "config.local.json"))
        data: dict[str, Any] = {}
        if config_path.exists():
            data = json.loads(config_path.read_text(encoding="utf-8"))

        artifact_dir = Path(
            os.getenv("KAPA_AGENT_ARTIFACT_DIR", data.get("artifact_dir", "artifacts"))
        )
        log_dir = Path(os.getenv("KAPA_AGENT_LOG_DIR", data.get("log_dir", "logs")))

        return cls(
            bind_host=os.getenv("KAPA_AGENT_BIND_HOST", data.get("bind_host", "127.0.0.1")),
            port=int(os.getenv("KAPA_AGENT_PORT", data.get("port", 8765))),
            artifact_dir=artifact_dir,
            log_dir=log_dir,
            auth_token=os.getenv("KAPA_AGENT_TOKEN", data.get("auth_token")),
            recipes=data.get("recipes", {}),
            default_window_patterns=data.get(
                "default_window_patterns",
                cls().default_window_patterns,
            ),
        )

    def ensure_dirs(self) -> None:
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

