#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import ctypes
import platform
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk


WDA_NONE = 0x0
WDA_MONITOR = 0x1
WDA_EXCLUDEFROMCAPTURE = 0x11


ROWS = [
    ("서울특별시 서초구 방배로 52", "토지", "1,234", "표준지", "테스트"),
    ("서울특별시 강남구 테헤란로 1", "상가", "2,345", "거래사례", "테스트"),
    ("경기도 성남시 분당구 판교역로 10", "아파트", "3,456", "평가사례", "테스트"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Local capture-protection simulator for KAPA probe testing.")
    parser.add_argument("--allow-capture", action="store_true", help="Do not set WDA_EXCLUDEFROMCAPTURE.")
    parser.add_argument("--title", default="KAPA HUB PLUS Capture Block Test")
    args = parser.parse_args()

    app = DemoApp(args.title, protect_capture=not args.allow_capture)
    app.run()
    return 0


class DemoApp:
    def __init__(self, title: str, protect_capture: bool) -> None:
        self.root = tk.Tk()
        self.root.title(title)
        self.root.geometry("920x560")
        self.root.minsize(760, 460)
        self.protect_capture = protect_capture
        self.status = tk.StringVar(value="Ready")
        self.search_text = tk.StringVar(value="서울특별시 서초구 방배로 52")
        self.capture_status = tk.StringVar(value="capture protection: pending")
        self.build_ui()

    def build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        header = ttk.Frame(self.root, padding=(12, 10))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)
        ttk.Label(header, text="KAPA HUB PLUS", font=("Segoe UI", 18, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(header, textvariable=self.capture_status).grid(row=0, column=1, sticky="e")

        search = ttk.Frame(self.root, padding=(12, 6))
        search.grid(row=1, column=0, sticky="ew")
        search.columnconfigure(1, weight=1)
        ttk.Label(search, text="주소").grid(row=0, column=0, padx=(0, 8))
        entry = ttk.Entry(search, textvariable=self.search_text)
        entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ttk.Button(search, text="검색", command=self.search).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(search, text="표 복사", command=self.copy_table).grid(row=0, column=3, padx=(0, 6))
        ttk.Button(search, text="CSV 내보내기", command=self.export_csv).grid(row=0, column=4)

        columns = ("address", "kind", "amount", "source", "note")
        self.tree = ttk.Treeview(self.root, columns=columns, show="headings")
        headings = {
            "address": "소재지",
            "kind": "종류",
            "amount": "가격",
            "source": "자료구분",
            "note": "비고",
        }
        widths = {
            "address": 360,
            "kind": 100,
            "amount": 120,
            "source": 140,
            "note": 120,
        }
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], anchor="w")
        self.tree.grid(row=2, column=0, sticky="nsew", padx=12, pady=(4, 8))

        status_bar = ttk.Frame(self.root, padding=(12, 8))
        status_bar.grid(row=3, column=0, sticky="ew")
        status_bar.columnconfigure(0, weight=1)
        ttk.Label(status_bar, textvariable=self.status).grid(row=0, column=0, sticky="w")

        self.populate(ROWS)
        self.root.after(250, self.apply_capture_protection)

    def populate(self, rows: list[tuple[str, str, str, str, str]]) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in rows:
            self.tree.insert("", "end", values=row)
        if rows:
            self.tree.selection_set(self.tree.get_children()[0])

    def search(self) -> None:
        query = self.search_text.get().strip()
        if not query:
            self.populate(ROWS)
            self.status.set("검색어 없음: 전체 테스트 데이터 표시")
            return
        rows = [row for row in ROWS if query in row[0]]
        if not rows:
            rows = [(query, "검색결과", "0", "시뮬레이션", "결과 없음")]
        self.populate(rows)
        self.status.set(f"검색 완료: {len(rows)}건")

    def copy_table(self) -> None:
        text = self.table_text()
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()
        self.status.set("표 데이터를 클립보드에 복사했습니다.")

    def export_csv(self) -> None:
        folder = Path.home() / "Documents"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"kapa_capture_block_test_{int(time.time())}.csv"
        with path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow(["소재지", "종류", "가격", "자료구분", "비고"])
            for item in self.tree.get_children():
                writer.writerow(self.tree.item(item, "values"))
        self.status.set(f"CSV 저장: {path}")

    def table_text(self) -> str:
        lines = ["소재지\t종류\t가격\t자료구분\t비고"]
        for item in self.tree.get_children():
            lines.append("\t".join(str(value) for value in self.tree.item(item, "values")))
        return "\n".join(lines)

    def apply_capture_protection(self) -> None:
        if not self.protect_capture:
            self.capture_status.set("capture protection: disabled")
            return
        if platform.system().lower() != "windows":
            self.capture_status.set("capture protection: unsupported OS")
            return
        hwnd = int(self.root.winfo_id())
        try:
            ok = ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
            if ok:
                self.capture_status.set("capture protection: WDA_EXCLUDEFROMCAPTURE")
            else:
                fallback_ok = ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_MONITOR)
                if fallback_ok:
                    self.capture_status.set("capture protection: WDA_MONITOR fallback")
                else:
                    self.capture_status.set("capture protection: failed")
        except Exception as exc:  # noqa: BLE001 - visible demo status is enough
            self.capture_status.set(f"capture protection: error {exc}")

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    raise SystemExit(main())
