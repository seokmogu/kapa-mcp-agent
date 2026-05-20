from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class WindowInfo(BaseModel):
    handle: int | None = None
    title: str
    class_name: str | None = None
    process_id: int | None = None
    process_name: str | None = None
    visible: bool | None = None


class WindowSelector(BaseModel):
    handle: int | None = None
    title_re: str | None = None
    title_contains: str | None = None
    process_name: str | None = None
    backend: Literal["uia", "win32"] = "uia"


class DumpRequest(BaseModel):
    selector: WindowSelector
    max_depth: int = Field(default=4, ge=0, le=12)
    max_nodes: int = Field(default=300, ge=1, le=3000)


class HotkeyRequest(BaseModel):
    keys: str = Field(description="pywinauto keyboard syntax, e.g. '^a', '^c', '{ENTER}'")
    selector: WindowSelector | None = None


class TypeTextRequest(BaseModel):
    text: str
    selector: WindowSelector | None = None
    paste: bool = True
    submit: bool = False


class ClickRequest(BaseModel):
    x: int
    y: int
    selector: WindowSelector | None = None
    button: Literal["left", "right", "middle"] = "left"


class ClipboardWriteRequest(BaseModel):
    text: str


class ScreenshotRequest(BaseModel):
    monitor: int = Field(default=1, ge=0)
    name: str = "screenshot.png"


class RecentFilesRequest(BaseModel):
    folders: list[str] = Field(default_factory=list)
    patterns: list[str] = Field(default_factory=lambda: ["*.xlsx", "*.xls", "*.csv", "*.pdf"])
    minutes: int = Field(default=30, ge=1, le=1440)
    limit: int = Field(default=20, ge=1, le=200)


class CollectFilesRequest(RecentFilesRequest):
    copy_to_artifacts: bool = True


class JobRequest(BaseModel):
    task: str
    program: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    outputs: list[str] = Field(default_factory=list)


class JobStatus(BaseModel):
    id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    task: str
    result: dict[str, Any] | None = None
    error: str | None = None


class ArtifactInfo(BaseModel):
    id: str
    name: str
    path: str
    size: int
    modified_at: float
