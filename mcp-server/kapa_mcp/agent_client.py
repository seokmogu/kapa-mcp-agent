from __future__ import annotations

import os
from typing import Any

import httpx


class AgentClient:
    def __init__(self, base_url: str, token: str | None = None, timeout: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    @classmethod
    def from_env(cls) -> "AgentClient":
        return cls(
            base_url=os.getenv("KAPA_AGENT_BASE_URL", "http://127.0.0.1:8765"),
            token=os.getenv("KAPA_AGENT_TOKEN"),
            timeout=float(os.getenv("KAPA_AGENT_TIMEOUT", "60")),
        )

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                self._url(path),
                params=params,
                headers=self._headers(),
            )
        response.raise_for_status()
        return response.json()

    async def get_bytes(self, path: str, params: dict[str, Any] | None = None) -> bytes:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                self._url(path),
                params=params,
                headers=self._headers(),
            )
        response.raise_for_status()
        return response.content

    async def post(self, path: str, json: dict[str, Any]) -> Any:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self._url(path),
                json=json,
                headers=self._headers(),
            )
        response.raise_for_status()
        return response.json()

    def _headers(self) -> dict[str, str]:
        if not self.token:
            return {}
        return {"X-Kapa-Agent-Token": self.token}

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path
