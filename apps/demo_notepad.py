"""示例 App:便签(演示如何接入工具箱,真实工具照此模板写)。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

from core.base_app import ToolApp


class NotepadApp(ToolApp):
    def build(self, root: QWidget) -> None:
        file: Path = self.data_path("notes.txt")

        frame = QWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.addWidget(frame)

        lay = QVBoxLayout(frame)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        text = QPlainTextEdit(frame)  # 默认按词换行
        f = QFont("Microsoft YaHei UI", 12)
        text.setFont(f)
        lay.addWidget(text, 1)

        status = QLabel("")
        status.setStyleSheet("color: #8a93a6;")
        lay.addWidget(status)

        if file.exists():
            text.setPlainText(file.read_text("utf-8"))

        def save():
            file.write_text(text.toPlainText(), "utf-8")
            status.setText(f"已保存到 {file}")
            self.log.info("notes saved, %d bytes", file.stat().st_size)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        save_btn = QPushButton("保存")
        save_btn.setFixedWidth(90)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(save)
        btn_row.addWidget(save_btn)
        lay.addLayout(btn_row)

        QShortcut(QKeySequence("Ctrl+S"), root, activated=save)

    def on_close(self) -> None:
        self.log.info("notepad closed")
