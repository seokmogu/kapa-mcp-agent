from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any
import re

import uvicorn
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse

from .config import AgentConfig
from .file_collector import collect_recent_files, info_for_path, recent_files
from .models import (
    ArtifactInfo,
    ClipboardWriteRequest,
    ClickRequest,
    CollectFilesRequest,
    DumpRequest,
    HotkeyRequest,
    JobRequest,
    JobStatus,
    RecentFilesRequest,
    ScreenshotRequest,
    TypeTextRequest,
    WindowInfo,
)
from .screen_capture import capture_screenshot
from .storage import ArtifactStore
from .windows_automation import AutomationUnavailable, WindowsAutomation, is_windows

config = AgentConfig.load()
config.ensure_dirs()
automation = WindowsAutomation()
artifacts = ArtifactStore(config.artifact_dir)
jobs: dict[str, JobStatus] = {}

app = FastAPI(title="KAPA Windows Agent", version="0.1.0")


def require_token(x_kapa_agent_token: str | None = Header(default=None)) -> None:
    if config.auth_token and x_kapa_agent_token != config.auth_token:
        raise HTTPException(status_code=401, detail="Invalid agent token")


Auth = Depends(require_token)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "platform": "windows" if is_windows() else "unsupported",
        "bind_host": config.bind_host,
        "port": config.port,
        "artifact_dir": str(config.artifact_dir),
        "recipes": sorted(config.recipes.keys()),
    }


@app.get("/recipes", dependencies=[Auth])
def list_recipes() -> dict[str, Any]:
    """List configured recipe names and a 1-line summary of each.

    The summary is a list of action names so MCP clients can discover what a
    recipe will do without re-reading the full config.
    """
    return {
        "recipes": {
            name: {
                "step_count": len(steps),
                "actions": [str(step.get("action")) for step in steps],
            }
            for name, steps in config.recipes.items()
        }
    }


@app.get("/diagnostics", dependencies=[Auth])
def diagnostics() -> dict[str, Any]:
    modules = {}
    for module_name in ["pywinauto", "pyperclip", "mss", "psutil"]:
        try:
            __import__(module_name)
            modules[module_name] = True
        except Exception:
            modules[module_name] = False
    return {
        "ok": True,
        "is_windows": is_windows(),
        "modules": modules,
        "artifact_dir_exists": config.artifact_dir.exists(),
        "log_dir_exists": config.log_dir.exists(),
        "window_patterns": config.default_window_patterns,
    }


@app.get("/windows", dependencies=[Auth])
def list_windows(backend: str = "uia") -> list[WindowInfo]:
    try:
        return automation.list_windows(backend=backend)
    except AutomationUnavailable as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


@app.get("/programs/{program}/probe", dependencies=[Auth])
def probe_program(program: str, backend: str = "uia") -> dict[str, Any]:
    title_pattern = config.default_window_patterns.get(program)
    if not title_pattern:
        raise HTTPException(status_code=404, detail=f"Unknown program pattern: {program}")
    try:
        windows = automation.list_windows(backend=backend)
    except AutomationUnavailable as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    regex = re.compile(title_pattern, re.IGNORECASE)
    matches = [window for window in windows if regex.match(window.title or "")]
    return {
        "program": program,
        "pattern": title_pattern,
        "matches": [item.model_dump() for item in matches],
    }


@app.post("/uia/dump", dependencies=[Auth])
def dump_uia(request: DumpRequest) -> dict[str, Any]:
    try:
        return automation.dump_tree(request.selector, request.max_depth, request.max_nodes)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/input/hotkey", dependencies=[Auth])
def hotkey(request: HotkeyRequest) -> dict[str, bool]:
    try:
        automation.hotkey(request.keys, request.selector)
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/input/type", dependencies=[Auth])
def type_text(request: TypeTextRequest) -> dict[str, bool]:
    try:
        automation.type_text(
            request.text,
            selector=request.selector,
            paste=request.paste,
            submit=request.submit,
        )
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/input/click", dependencies=[Auth])
def click(request: ClickRequest) -> dict[str, bool]:
    try:
        automation.click(request.x, request.y, selector=request.selector, button=request.button)
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/clipboard", dependencies=[Auth])
def read_clipboard() -> dict[str, str]:
    return {"text": automation.read_clipboard()}


@app.post("/clipboard", dependencies=[Auth])
def write_clipboard(request: ClipboardWriteRequest) -> dict[str, bool]:
    automation.write_clipboard(request.text)
    return {"ok": True}


@app.post("/screen/screenshot", dependencies=[Auth])
def screenshot(request: ScreenshotRequest) -> dict[str, Any]:
    try:
        return capture_screenshot(artifacts, request.monitor, request.name)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/files/recent", dependencies=[Auth])
def files_recent(request: RecentFilesRequest) -> list[ArtifactInfo]:
    return [
        info_for_path(path)
        for path in recent_files(request.folders, request.patterns, request.minutes, request.limit)
    ]


@app.post("/files/collect", dependencies=[Auth])
def files_collect(request: CollectFilesRequest) -> list[ArtifactInfo]:
    if not request.copy_to_artifacts:
        return files_recent(request)
    return collect_recent_files(
        artifacts,
        request.folders,
        request.patterns,
        request.minutes,
        request.limit,
    )


@app.get("/artifacts", dependencies=[Auth])
def list_artifacts() -> list[ArtifactInfo]:
    return artifacts.list()


@app.get("/artifacts/{artifact_id}", dependencies=[Auth])
def get_artifact(artifact_id: str) -> FileResponse:
    path = artifacts.path_for_id(artifact_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(path)


@app.post("/jobs", dependencies=[Auth])
def create_job(request: JobRequest, background_tasks: BackgroundTasks) -> JobStatus:
    job_id = uuid.uuid4().hex
    job = JobStatus(id=job_id, status="queued", task=request.task)
    jobs[job_id] = job
    background_tasks.add_task(run_job, job_id, request)
    return job


@app.get("/jobs/{job_id}", dependencies=[Auth])
def get_job(job_id: str) -> JobStatus:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def run_job(job_id: str, request: JobRequest) -> None:
    jobs[job_id].status = "running"
    try:
        result = execute_job(request, job_id=job_id)
        jobs[job_id].result = result
        if isinstance(result, dict) and result.get("ok") is False:
            jobs[job_id].status = "failed"
            jobs[job_id].error = str(
                result.get("error") or result.get("reason") or "recipe_failed"
            )
        else:
            jobs[job_id].status = "succeeded"
    except Exception as exc:  # noqa: BLE001 - background job should persist failure reason
        jobs[job_id].status = "failed"
        jobs[job_id].error = str(exc)


def execute_job(request: JobRequest, job_id: str | None = None) -> dict[str, Any]:
    if request.task == "run_recipe":
        recipe_name = str(request.params["recipe"])
        steps = config.recipes.get(recipe_name)
        if not steps:
            return {
                "ok": False,
                "reason": "recipe_not_configured",
                "recipe": recipe_name,
            }
        result = automation.run_recipe(steps, request.params)
        _persist_recipe_trace(result, recipe_name, request.params, job_id)
        _maybe_save_clipboard_artifact(result, recipe_name, request.params)
        return result

    if request.task == "search_address":
        program = request.program or "kapa_hub_plus"
        recipe_name = f"{program}.search_address"
        steps = config.recipes.get(recipe_name)
        if not steps:
            return {
                "ok": False,
                "reason": "recipe_not_configured",
                "recipe": recipe_name,
                "next_step": (
                    "Capture UI selectors on Windows and add this recipe to "
                    "config.local.json."
                ),
            }
        result = automation.run_recipe(steps, request.params)
        _persist_recipe_trace(result, recipe_name, request.params, job_id)
        _maybe_save_clipboard_artifact(result, recipe_name, request.params)
        return result

    if request.task == "dump_windows":
        return {"windows": [item.model_dump() for item in automation.list_windows()]}

    raise ValueError(f"Unknown task: {request.task}")


def _persist_recipe_trace(
    result: dict[str, Any],
    recipe_name: str,
    params: dict[str, Any],
    job_id: str | None,
) -> None:
    """Save the recipe trace as a JSON artifact and link it back in result.

    Trace artifacts are the primary debug surface for KAPA/KAIS calibration —
    they record per-step timing, the (interpolated) step body, and the exact
    error type/message when a step fails. Saved on both success and failure.
    """
    try:
        trace_doc = {
            "recipe": recipe_name,
            "params": params,
            "job_id": job_id,
            "saved_at": time.time(),
            "result": {
                "ok": result.get("ok"),
                "error": result.get("error"),
                "failed_at": result.get("failed_at"),
                "started_at": result.get("started_at"),
                "finished_at": result.get("finished_at"),
                "total_duration_ms": result.get("total_duration_ms"),
                "steps": result.get("steps", []),
                # values are intentionally summarized only; full text artifact
                # is saved separately by _maybe_save_clipboard_artifact.
                "value_keys": list((result.get("values") or {}).keys()),
            },
        }
        artifact = artifacts.save_text(
            f"trace_{recipe_name}_{job_safe_name(params.get('address', job_id or 'run'))}.json",
            json.dumps(trace_doc, ensure_ascii=False, indent=2),
        )
        result["trace_artifact"] = artifact.model_dump()
    except Exception as exc:  # noqa: BLE001 - trace persistence must never break a job
        result["trace_error"] = repr(exc)


def _maybe_save_clipboard_artifact(
    result: dict[str, Any], recipe_name: str, params: dict[str, Any]
) -> None:
    clipboard = (result.get("values") or {}).get("clipboard")
    if not clipboard:
        return
    artifact = artifacts.save_text(
        f"{recipe_name}_{job_safe_name(params.get('address', 'result'))}.txt",
        clipboard,
    )
    result["artifact"] = artifact.model_dump()


def job_safe_name(value: Any) -> str:
    text = str(value)
    return "".join(ch if ch.isalnum() else "_" for ch in text)[:80] or "result"


def run() -> None:
    uvicorn.run(app, host=config.bind_host, port=config.port)


if __name__ == "__main__":
    run()
