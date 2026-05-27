from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


AGENT_VERSION = "0.2.0"


@dataclass(slots=True)
class GitHubConfig:
    """Settings for pulling recipe/agent updates from a GitHub repo.

    The token is read-only and must live ONLY in config.local.json (gitignored)
    or the KAPA_AGENT_GITHUB_TOKEN env var. It is never written back to disk by
    the agent and never logged.
    """

    repo: str = "seokmogu/kapa-mcp-agent"
    ref: str = "main"
    token: str | None = None
    asset_name: str = "kapa-agent.exe"

    @property
    def configured(self) -> bool:
        return bool(self.repo)


@dataclass(slots=True)
class AgentConfig:
    bind_host: str = "127.0.0.1"
    port: int = 8765
    artifact_dir: Path = Path("artifacts")
    log_dir: Path = Path("logs")
    recipes_dir: Path = Path("recipes")
    config_path: Path = Path("config.local.json")
    auth_token: str | None = None
    recipes: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    github: GitHubConfig = field(default_factory=GitHubConfig)
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
            data = json.loads(config_path.read_text(encoding="utf-8-sig"))

        artifact_dir = Path(
            os.getenv("KAPA_AGENT_ARTIFACT_DIR", data.get("artifact_dir", "artifacts"))
        )
        log_dir = Path(os.getenv("KAPA_AGENT_LOG_DIR", data.get("log_dir", "logs")))
        recipes_dir = Path(
            os.getenv("KAPA_AGENT_RECIPES_DIR", data.get("recipes_dir", "recipes"))
        )

        github_data = data.get("github", {}) or {}
        github = GitHubConfig(
            repo=os.getenv("KAPA_AGENT_GITHUB_REPO", github_data.get("repo", "seokmogu/kapa-mcp-agent")),
            ref=os.getenv("KAPA_AGENT_GITHUB_REF", github_data.get("ref", "main")),
            token=os.getenv("KAPA_AGENT_GITHUB_TOKEN", github_data.get("token")),
            asset_name=os.getenv(
                "KAPA_AGENT_GITHUB_ASSET", github_data.get("asset_name", "kapa-agent.exe")
            ),
        )

        config = cls(
            bind_host=os.getenv("KAPA_AGENT_BIND_HOST", data.get("bind_host", "127.0.0.1")),
            port=int(os.getenv("KAPA_AGENT_PORT", data.get("port", 8765))),
            artifact_dir=artifact_dir,
            log_dir=log_dir,
            recipes_dir=recipes_dir,
            config_path=config_path,
            auth_token=os.getenv("KAPA_AGENT_TOKEN", data.get("auth_token")),
            recipes={},
            github=github,
            default_window_patterns=data.get(
                "default_window_patterns",
                cls().default_window_patterns,
            ),
        )
        config.recipes = config._merge_recipes(data.get("recipes", {}))
        return config

    def _merge_recipes(
        self, inline_recipes: dict[str, list[dict[str, Any]]]
    ) -> dict[str, list[dict[str, Any]]]:
        """Merge recipes from recipes_dir/*.json with inline config recipes.

        Precedence (later wins): recipes_dir files < inline config recipes.
        Files ending in .template.json are ignored (they are documentation
        scaffolding, not active recipes).
        """
        merged: dict[str, list[dict[str, Any]]] = {}
        merged.update(load_recipe_dir(self.recipes_dir))
        # inline recipes override file-based ones, allowing live experimentation
        for name, steps in (inline_recipes or {}).items():
            merged[name] = steps
        return merged

    def reload_recipes(self) -> dict[str, list[dict[str, Any]]]:
        """Re-read recipes from disk (recipes_dir + inline config) into memory."""
        data: dict[str, Any] = {}
        if self.config_path.exists():
            data = json.loads(self.config_path.read_text(encoding="utf-8-sig"))
        self.recipes = self._merge_recipes(data.get("recipes", {}))
        return self.recipes

    def recipes_hash(self) -> str:
        """Stable short hash of the active recipe set, for version reporting."""
        blob = json.dumps(self.recipes, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]

    def ensure_dirs(self) -> None:
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)


def load_recipe_dir(recipes_dir: Path) -> dict[str, list[dict[str, Any]]]:
    """Load active recipe files from a directory.

    Each recipe file is JSON of the form
    ``{"name": "...", "description": "...", "steps": [...]}``. The recipe name
    defaults to the filename stem if "name" is absent. ``*.template.json`` files
    are skipped.
    """
    result: dict[str, list[dict[str, Any]]] = {}
    if not recipes_dir.exists() or not recipes_dir.is_dir():
        return result
    for path in sorted(recipes_dir.glob("*.json")):
        if path.name.endswith(".template.json"):
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        if isinstance(doc, list):
            # bare list of steps; name from filename
            result[path.stem] = doc
            continue
        if not isinstance(doc, dict):
            continue
        name = str(doc.get("name") or path.stem)
        steps = doc.get("steps", [])
        if isinstance(steps, list):
            result[name] = steps
    return result
