from __future__ import annotations

import os
import platform
import re
import time
from typing import Any

from .models import WindowInfo, WindowSelector


def is_windows() -> bool:
    return platform.system().lower() == "windows"


class AutomationUnavailable(RuntimeError):
    pass


class WindowsAutomation:
    def ensure_available(self) -> None:
        if not is_windows():
            raise AutomationUnavailable("Windows UI automation is only available on Windows.")

    def list_windows(self, backend: str = "uia") -> list[WindowInfo]:
        self.ensure_available()
        from pywinauto import Desktop

        windows = []
        for win in Desktop(backend=backend).windows():
            info = win.element_info
            process_name = self._process_name(getattr(info, "process_id", None))
            windows.append(
                WindowInfo(
                    handle=getattr(info, "handle", None),
                    title=win.window_text(),
                    class_name=getattr(info, "class_name", None),
                    process_id=getattr(info, "process_id", None),
                    process_name=process_name,
                    visible=win.is_visible(),
                )
            )
        return windows

    def dump_tree(self, selector: WindowSelector, max_depth: int, max_nodes: int) -> dict[str, Any]:
        self.ensure_available()
        win = self.find_window(selector)
        count = 0

        def walk(control: Any, depth: int) -> dict[str, Any]:
            nonlocal count
            count += 1
            info = control.element_info
            node: dict[str, Any] = {
                "name": getattr(info, "name", "") or control.window_text(),
                "control_type": getattr(info, "control_type", None),
                "automation_id": getattr(info, "automation_id", None),
                "class_name": getattr(info, "class_name", None),
                "handle": getattr(info, "handle", None),
                "rectangle": str(getattr(info, "rectangle", "")),
            }
            if depth < max_depth and count < max_nodes:
                children = []
                for child in control.children():
                    if count >= max_nodes:
                        break
                    children.append(walk(child, depth + 1))
                if children:
                    node["children"] = children
            return node

        return walk(win, 0)

    def focus(self, selector: WindowSelector | None) -> None:
        if selector is None:
            return
        win = self.find_window(selector)
        win.set_focus()
        time.sleep(0.2)

    def hotkey(self, keys: str, selector: WindowSelector | None = None) -> None:
        self.ensure_available()
        self.focus(selector)
        from pywinauto.keyboard import send_keys

        send_keys(keys)

    def type_text(
        self,
        text: str,
        selector: WindowSelector | None = None,
        paste: bool = True,
        submit: bool = False,
    ) -> None:
        self.ensure_available()
        self.focus(selector)
        if paste:
            import pyperclip
            from pywinauto.keyboard import send_keys

            pyperclip.copy(text)
            send_keys("^v")
        else:
            from pywinauto.keyboard import send_keys

            send_keys(text, with_spaces=True)
        if submit:
            from pywinauto.keyboard import send_keys

            send_keys("{ENTER}")

    def click(self, x: int, y: int, selector: WindowSelector | None = None, button: str = "left") -> None:
        self.ensure_available()
        self.focus(selector)
        from pywinauto import mouse

        mouse.click(button=button, coords=(x, y))

    def read_clipboard(self) -> str:
        import pyperclip

        return pyperclip.paste()

    def write_clipboard(self, text: str) -> None:
        import pyperclip

        pyperclip.copy(text)

    def find_window(self, selector: WindowSelector) -> Any:
        self.ensure_available()
        from pywinauto import Desktop

        desktop = Desktop(backend=selector.backend)
        if selector.handle is not None:
            return desktop.window(handle=selector.handle)
        if selector.title_re:
            return desktop.window(title_re=selector.title_re)

        candidates = desktop.windows()
        for win in candidates:
            title = win.window_text()
            info = win.element_info
            if selector.title_contains and selector.title_contains not in title:
                continue
            if selector.process_name:
                process_name = self._process_name(getattr(info, "process_id", None))
                if process_name and process_name.lower() != selector.process_name.lower():
                    continue
            return win
        raise LookupError(f"No window matched selector: {selector.model_dump()}")

    def find_window_by_pattern(self, title_pattern: str, backend: str = "uia") -> Any:
        return self.find_window(WindowSelector(title_re=title_pattern, backend=backend))

    def run_recipe(self, steps: list[dict[str, Any]], context: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {"steps": [], "values": {}}
        for index, raw_step in enumerate(steps):
            step = self._interpolate(raw_step, context)
            action = step.get("action")
            try:
                if action == "wait":
                    time.sleep(float(step.get("seconds", 1)))
                elif action == "hotkey":
                    self.hotkey(str(step["keys"]), self._selector_from_step(step))
                elif action == "type_text":
                    self.type_text(
                        str(step.get("text", "")),
                        selector=self._selector_from_step(step),
                        paste=bool(step.get("paste", True)),
                        submit=bool(step.get("submit", False)),
                    )
                elif action == "click":
                    self.click(
                        int(step["x"]),
                        int(step["y"]),
                        selector=self._selector_from_step(step),
                        button=str(step.get("button", "left")),
                    )
                elif action == "read_clipboard":
                    key = str(step.get("save_as", "clipboard"))
                    result["values"][key] = self.read_clipboard()
                elif action == "write_clipboard":
                    self.write_clipboard(str(step.get("text", "")))
                else:
                    raise ValueError(f"Unknown recipe action: {action}")
                result["steps"].append({"index": index, "action": action, "ok": True})
            except Exception as exc:  # noqa: BLE001 - recipe runner must report exact failed step
                result["steps"].append(
                    {"index": index, "action": action, "ok": False, "error": str(exc)}
                )
                raise
        return result

    def _selector_from_step(self, step: dict[str, Any]) -> WindowSelector | None:
        selector_data = step.get("selector")
        if not selector_data:
            return None
        return WindowSelector(**selector_data)

    def _interpolate(self, value: Any, context: dict[str, Any]) -> Any:
        if isinstance(value, str):
            for key, replacement in context.items():
                value = value.replace("{{" + key + "}}", str(replacement))
            return value
        if isinstance(value, list):
            return [self._interpolate(item, context) for item in value]
        if isinstance(value, dict):
            return {key: self._interpolate(item, context) for key, item in value.items()}
        return value

    @staticmethod
    def _process_name(process_id: int | None) -> str | None:
        if process_id is None:
            return None
        try:
            import psutil

            return psutil.Process(process_id).name()
        except Exception:
            return None

