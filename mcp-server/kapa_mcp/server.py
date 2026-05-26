from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .agent_client import AgentClient

mcp = FastMCP("kapa-control")


def client() -> AgentClient:
    return AgentClient.from_env()


@mcp.tool()
async def agent_health() -> dict[str, Any]:
    """Check whether the Windows Agent is reachable."""
    return await client().get("/health")


@mcp.tool()
async def agent_diagnostics() -> dict[str, Any]:
    """Check Windows Agent dependencies and configured program patterns."""
    return await client().get("/diagnostics")


@mcp.tool()
async def list_recipes() -> dict[str, Any]:
    """List recipe names configured on the Windows Agent and their step actions."""
    return await client().get("/recipes")


@mcp.tool()
async def list_windows(backend: str = "uia") -> list[dict[str, Any]]:
    """List top-level Windows desktop windows visible to the agent session."""
    return await client().get("/windows", params={"backend": backend})


@mcp.tool()
async def probe_program(program: str = "kapa_hub_plus", backend: str = "uia") -> dict[str, Any]:
    """Find visible windows matching a configured program pattern."""
    return await client().get(f"/programs/{program}/probe", params={"backend": backend})


@mcp.tool()
async def dump_uia(
    title_re: str | None = None,
    title_contains: str | None = None,
    handle: int | None = None,
    process_name: str | None = None,
    backend: str = "uia",
    max_depth: int = 4,
    max_nodes: int = 300,
) -> dict[str, Any]:
    """Dump a UI Automation tree for a selected window."""
    return await client().post(
        "/uia/dump",
        {
            "selector": {
                "handle": handle,
                "title_re": title_re,
                "title_contains": title_contains,
                "process_name": process_name,
                "backend": backend,
            },
            "max_depth": max_depth,
            "max_nodes": max_nodes,
        },
    )


@mcp.tool()
async def send_hotkey(
    keys: str,
    title_re: str | None = None,
    title_contains: str | None = None,
    handle: int | None = None,
) -> dict[str, Any]:
    """Send a pywinauto hotkey string such as '^a', '^c', or '{ENTER}'."""
    return await client().post(
        "/input/hotkey",
        {
            "keys": keys,
            "selector": _selector(title_re, title_contains, handle),
        },
    )


@mcp.tool()
async def type_text(
    text: str,
    title_re: str | None = None,
    title_contains: str | None = None,
    handle: int | None = None,
    paste: bool = True,
    submit: bool = False,
) -> dict[str, Any]:
    """Type text into the selected window, using clipboard paste by default."""
    return await client().post(
        "/input/type",
        {
            "text": text,
            "selector": _selector(title_re, title_contains, handle),
            "paste": paste,
            "submit": submit,
        },
    )


@mcp.tool()
async def click_screen(
    x: int,
    y: int,
    title_re: str | None = None,
    title_contains: str | None = None,
    handle: int | None = None,
    button: str = "left",
) -> dict[str, Any]:
    """Click absolute screen coordinates from the Windows desktop session."""
    return await client().post(
        "/input/click",
        {
            "x": x,
            "y": y,
            "selector": _selector(title_re, title_contains, handle),
            "button": button,
        },
    )


@mcp.tool()
async def read_clipboard() -> dict[str, str]:
    """Read text from the Windows clipboard."""
    return await client().get("/clipboard")


@mcp.tool()
async def write_clipboard(text: str) -> dict[str, Any]:
    """Write text to the Windows clipboard."""
    return await client().post("/clipboard", {"text": text})


@mcp.tool()
async def capture_screenshot(monitor: int = 1, name: str = "screenshot.png") -> dict[str, Any]:
    """Capture a diagnostic screenshot and report black-pixel ratio."""
    return await client().post(
        "/screen/screenshot",
        {
            "monitor": monitor,
            "name": name,
        },
    )


@mcp.tool()
async def recent_export_files(
    folders: list[str] | None = None,
    patterns: list[str] | None = None,
    minutes: int = 30,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """List recent XLSX/PDF/CSV-style files in likely export folders."""
    return await client().post(
        "/files/recent",
        {
            "folders": folders or [],
            "patterns": patterns or ["*.xlsx", "*.xls", "*.csv", "*.pdf"],
            "minutes": minutes,
            "limit": limit,
        },
    )


@mcp.tool()
async def collect_export_files(
    folders: list[str] | None = None,
    patterns: list[str] | None = None,
    minutes: int = 30,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Copy recent export files into the agent artifact store."""
    return await client().post(
        "/files/collect",
        {
            "folders": folders or [],
            "patterns": patterns or ["*.xlsx", "*.xls", "*.csv", "*.pdf"],
            "minutes": minutes,
            "limit": limit,
            "copy_to_artifacts": True,
        },
    )


@mcp.tool()
async def search_address(
    address: str,
    program: str = "kapa_hub_plus",
    outputs: list[str] | None = None,
) -> dict[str, Any]:
    """Start a recipe-backed address search job on KAPA HUB PLUS or KAIS."""
    return await client().post(
        "/jobs",
        {
            "task": "search_address",
            "program": program,
            "params": {"address": address},
            "outputs": outputs or ["clipboard", "export_file"],
        },
    )


@mcp.tool()
async def run_recipe(recipe: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run a named recipe configured in the Windows Agent config."""
    merged = {"recipe": recipe}
    if params:
        merged.update(params)
    return await client().post(
        "/jobs",
        {
            "task": "run_recipe",
            "params": merged,
            "outputs": [],
        },
    )


@mcp.tool()
async def get_job(job_id: str) -> dict[str, Any]:
    """Get job status and result from the Windows Agent."""
    return await client().get(f"/jobs/{job_id}")


@mcp.tool()
async def list_artifacts() -> list[dict[str, Any]]:
    """List artifacts collected by the Windows Agent."""
    return await client().get("/artifacts")


@mcp.tool()
async def read_artifact_text(artifact_id: str, encoding: str = "utf-8") -> dict[str, Any]:
    """Read a text artifact by id. Use for clipboard dumps and text exports."""
    content = await client().get_bytes(f"/artifacts/{artifact_id}")
    return {
        "artifact_id": artifact_id,
        "encoding": encoding,
        "text": content.decode(encoding, errors="replace"),
    }


def _selector(
    title_re: str | None,
    title_contains: str | None,
    handle: int | None,
) -> dict[str, Any] | None:
    if title_re is None and title_contains is None and handle is None:
        return None
    return {
        "handle": handle,
        "title_re": title_re,
        "title_contains": title_contains,
        "backend": "uia",
    }


def run() -> None:
    mcp.run()


if __name__ == "__main__":
    run()
