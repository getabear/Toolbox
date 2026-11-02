"""示例 App:便签(演示如何接入工具箱,真实工具照此模板写)。"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path

try:
    import customtkinter as ctk
    HAS_CTK = True
except ImportError:
    HAS_CTK = False

from core.base_app import ToolApp


class NotepadApp(ToolApp):
    def build(self, root: tk.Misc) -> None:
        file: Path = self.data_path("notes.txt")

        if HAS_CTK:
            frame = ctk.CTkFrame(root, fg_color="transparent")
            frame.pack(fill="both", expand=True, padx=16, pady=16)
            text = ctk.CTkTextbox(frame, wrap="word", font=("Microsoft YaHei UI", 14))
            text.pack(fill="both", expand=True)
            status = ctk.CTkLabel(frame, text="", anchor="w")
            status.pack(fill="x", pady=(6, 0))
        else:
            frame = tk.Frame(root)
            frame.pack(fill="both", expand=True, padx=16, pady=16)
            text = tk.Text(frame, wrap="word", font=("Microsoft YaHei UI", 14))
            text.pack(fill="both", expand=True)
            status = tk.Label(frame, text="", anchor="w")
            status.pack(fill="x", pady=(6, 0))

        if file.exists():
            text.insert("1.0", file.read_text("utf-8"))

        def save(_=None):
            file.write_text(text.get("1.0", "end-1c"), "utf-8")
            status.configure(text=f"已保存到 {file}")
            self.log.info("notes saved, %d bytes", file.stat().st_size)

        if HAS_CTK:
            ctk.CTkButton(frame, text="保存", command=save, width=90).pack(anchor="e", pady=(8, 0))
        else:
            tk.Button(frame, text="保存", command=save).pack(anchor="e", pady=(8, 0))
        root.bind("<Control-s>", save)

    def on_close(self) -> None:
        self.log.info("notepad closed")
