from __future__ import annotations

from pathlib import Path

from .models import ArtifactInfo
from .storage import ArtifactStore


def capture_screenshot(artifact_store: ArtifactStore, monitor: int, name: str) -> dict[str, object]:
    import mss
    import mss.tools

    with mss.mss() as screen:
        if monitor >= len(screen.monitors):
            raise ValueError(f"Monitor {monitor} not available. Found {len(screen.monitors) - 1} monitors.")
        shot = screen.grab(screen.monitors[monitor])
        png = mss.tools.to_png(shot.rgb, shot.size)

    info = artifact_store.save_bytes(name, png)
    return {
        "artifact": info.model_dump(),
        "width": shot.width,
        "height": shot.height,
        "black_ratio": estimate_black_ratio(shot.rgb),
    }


def estimate_black_ratio(rgb: bytes) -> float:
    if not rgb:
        return 0.0
    pixel_count = len(rgb) // 3
    if pixel_count == 0:
        return 0.0
    black = 0
    for index in range(0, len(rgb), 3):
        if rgb[index] < 8 and rgb[index + 1] < 8 and rgb[index + 2] < 8:
            black += 1
    return round(black / pixel_count, 4)

