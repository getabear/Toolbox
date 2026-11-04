"""
每日任务 —— 轻量 Todo 工具。

特性:
  · 顶部输入框回车/点按钮快速添加;每条任务有 🗑 删除
  · 点击任务即完成 → 弹出随机鼓励语 toast;完成的任务自动隐藏
  · 「已完成」页面查看所有历史完成记录(可还原/彻底删除)
  · 超过 N 天未完成的旧任务在列表顶部亮橙色提醒
  · 数据 JSON 持久化到受管环境 env.data_dir/tasks.json
"""
from __future__ import annotations

import json
import random
import time
import uuid

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from core.base_app import ToolApp

ENCOURAGEMENTS = [
    "🎉 干得漂亮!又搞定一件事!",
    "💪 太强了,执行力拉满!",
    "✨ 完成比完美更重要,你做到了!",
    "🚀 进度 +1,离目标又近了一步!",
    "🌟 今天的你比昨天更厉害!",
    "🏆 稳!这就是高手的节奏!",
    "🔥 又划掉一条,爽不爽?",
    "🌈 积少成多,你在悄悄变强!",
    "👏 给自己鼓个掌,值得!",
    "⭐ 优秀的习惯正在养成中!",
]

STALE_DAYS = 3          # 超过几天未完成算"旧任务"
SECONDS_PER_DAY = 86400


class TaskRow(QFrame):
    """单条任务行:点击标题区完成,右侧按钮删除/还原。"""

    def __init__(self, t: dict, done: bool, stale: bool, days_old: int,
                 on_complete, on_delete, on_restore, parent=None):
        super().__init__(parent)
        self.setObjectName("taskRow")
        bg = "#232833" if not stale else "#2e2618"
        border = "#e8a54b" if stale else "#2a2f3a"
        self.setStyleSheet(f"""
            QFrame#taskRow {{
                background: {bg}; border: 1px solid {border}; border-radius: 10px;
            }}
            QFrame#taskRow QLabel {{ background: transparent; border: none; }}
        """)

        if done:
            when = time.strftime("%m-%d %H:%M", time.localtime(t["done_at"]))
            text = f"✔ {t['title']}"
            sub = f"完成于 {when}"
            color = "#5c6474"
        else:
            text = ("⚠ " if stale else "") + t["title"]
            age = f" · {days_old}天前添加" if stale else ""
            sub = (f"{time.strftime('%m-%d %H:%M', time.localtime(t['created']))} 创建{age}")
            color = "#e8a54b" if stale else "#e6e9ef"

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 8, 8, 8)
        lay.setSpacing(6)

        texts = QVBoxLayout()
        texts.setSpacing(1)
        main_lb = QLabel(text)
        main_lb.setStyleSheet(f"color: {color}; font-size: 14px;")
        sub_lb = QLabel(sub)
        sub_lb.setStyleSheet("color: #6a7385; font-size: 11px;")
        texts.addWidget(main_lb)
        texts.addWidget(sub_lb)
        lay.addLayout(texts, 1)

        if not done:
            # 点标题即完成:文本区鼠标穿透到行容器
            main_lb.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            sub_lb.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            self.setCursor(Qt.PointingHandCursor)
            self._on_click = lambda: on_complete(t["id"])
            ok = QPushButton("✔ 完成")
            ok.setProperty("kind", "ok")
            ok.setFixedSize(76, 26)
            ok.clicked.connect(lambda: on_complete(t["id"]))
            lay.addWidget(ok)
        else:
            self._on_click = None
            rs = QPushButton("↩ 还原")
            rs.setProperty("kind", "dim")
            rs.setFixedSize(76, 26)
            rs.clicked.connect(lambda: on_restore(t["id"]))
            lay.addWidget(rs)

        dele = QPushButton("🗑")
        dele.setProperty("kind", "danger")
        dele.setFixedSize(40, 26)
        dele.clicked.connect(lambda: on_delete(t["id"]))
        lay.addWidget(dele)

    def mousePressEvent(self, ev):
        if self._on_click and ev.button() == Qt.LeftButton:
            self._on_click()


class DailyTasksApp(ToolApp):
    # ---------- 数据层(纯逻辑,可独立测试) ----------
    def _load(self) -> list[dict]:
        f = self.env.data_dir / "tasks.json"
        if f.exists():
            try:
                return json.loads(f.read_text("utf-8"))
            except (json.JSONDecodeError, OSError):
                self.log.warning("tasks.json corrupted, starting fresh")
        return []

    def _save(self):
        f = self.env.data_dir / "tasks.json"
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.tasks, ensure_ascii=False, indent=2), "utf-8")
        tmp.replace(f)

    def add_task(self, title: str) -> dict | None:
        title = (title or "").strip()
        if not title:
            return None
        task = {"id": uuid.uuid4().hex[:10], "title": title,
                "created": int(time.time()), "done": False, "done_at": None}
        self.tasks.append(task)
        self._save()
        self.log.info("task added: %s", title)
        return task

    def remove_task(self, task_id: str):
        self.tasks = [t for t in self.tasks if t["id"] != task_id]
        self._save()

    def complete_task(self, task_id: str) -> str | None:
        """完成任务,返回鼓励语;找不到返回 None。"""
        for t in self.tasks:
            if t["id"] == task_id and not t["done"]:
                t["done"] = True
                t["done_at"] = int(time.time())
                self._save()
                self.log.info("task done: %s", t["title"])
                return random.choice(ENCOURAGEMENTS)
        return None

    def uncomplete_task(self, task_id: str):
        for t in self.tasks:
            if t["id"] == task_id:
                t["done"] = False
                t["done_at"] = None
        self._save()

    def pending_tasks(self) -> list[dict]:
        """未完成,旧任务排前。"""
        now = time.time()
        p = [t for t in self.tasks if not t["done"]]
        p.sort(key=lambda t: (now - t["created"] < STALE_DAYS * SECONDS_PER_DAY, t["created"]))
        return p

    def done_tasks(self) -> list[dict]:
        d = [t for t in self.tasks if t["done"]]
        d.sort(key=lambda t: t["done_at"] or 0, reverse=True)
        return d

    def is_stale(self, task: dict) -> bool:
        return (not task["done"] and
                time.time() - task["created"] >= STALE_DAYS * SECONDS_PER_DAY)

    def days_old(self, task: dict) -> int:
        return int((time.time() - task["created"]) // SECONDS_PER_DAY)

    # ---------- UI ----------
    def build(self, root: QWidget) -> None:
        self.tasks = self._load()
        self._page = "pending"
        self._toast_widget: QLabel | None = None

        wrap = QWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.addWidget(wrap)

        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        # 顶部:添加 + 页面切换
        top = QWidget()
        top.setStyleSheet("background: transparent;")
        tl = QHBoxLayout(top)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(8)

        self.entry = QLineEdit()
        self.entry.setObjectName("searchBox")   # 复用主程序搜索框样式
        self.entry.setFixedHeight(38)
        self.entry.setPlaceholderText("✏️ 输入任务,回车快速添加…")
        self.entry.returnPressed.connect(self._on_add)
        tl.addWidget(self.entry, 1)

        add_btn = QPushButton("＋ 添加")
        add_btn.setFixedWidth(90)
        add_btn.clicked.connect(self._on_add)
        tl.addWidget(add_btn)

        self.pending_btn = QPushButton("📋 待办")
        self.pending_btn.setFixedWidth(80)
        self.pending_btn.clicked.connect(lambda: self._switch("pending"))
        tl.addWidget(self.pending_btn)

        self.done_btn = QPushButton("✅ 已完成")
        self.done_btn.setFixedWidth(90)
        self.done_btn.clicked.connect(lambda: self._switch("done"))
        tl.addWidget(self.done_btn)
        lay.addWidget(top)

        # 统计条 + 提醒横幅
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: #8a93a6; font-size: 12px;")
        lay.addWidget(self.stats_label)

        self.banner = QLabel("")
        self.banner.setStyleSheet("color: #e8a54b; font-size: 13px;")
        self.banner.hide()
        lay.addWidget(self.banner)

        # 列表(滚动)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.list_host = QWidget()
        self.list_lay = QVBoxLayout(self.list_host)
        self.list_lay.setContentsMargins(0, 0, 8, 0)
        self.list_lay.setSpacing(6)
        self.list_lay.addStretch(1)
        scroll.setWidget(self.list_host)
        lay.addWidget(scroll, 1)

        self._update_page_buttons()
        self._render()

    # ---- 交互 ----
    def _switch(self, page: str):
        self._page = page
        self._update_page_buttons()
        self._render()

    def _update_page_buttons(self):
        for btn, pg in ((self.pending_btn, "pending"), (self.done_btn, "done")):
            btn.setProperty("kind", "page")
            btn.setProperty("active", "true" if self._page == pg else "false")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {"#4f8cff" if self._page == pg else "#2a2f3a"};
                    color: {"white" if self._page == pg else "#e6e9ef"};
                    border: none; border-radius: 8px; padding: 7px 10px; font-size: 13px;
                }}
                QPushButton:hover {{ background: {"#6ba0ff" if self._page == pg else "#3a4150"}; }}
            """)

    def _on_add(self):
        title = self.entry.text().strip()
        if not title:
            return
        self.add_task(title)
        self.entry.clear()
        self._page = "pending"
        self._update_page_buttons()
        self._render()

    def _on_complete(self, task_id: str):
        msg = self.complete_task(task_id)
        if msg:
            self._show_toast(msg)
        self._render()

    def _on_delete(self, task_id: str):
        self.remove_task(task_id)
        self._render()

    def _on_restore(self, task_id: str):
        self.uncomplete_task(task_id)
        self._render()

    # ---- 渲染 ----
    def _render(self):
        # 清空旧行(保留末尾 stretch)
        while self.list_lay.count() > 1:
            item = self.list_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        pending = self.pending_tasks()
        done = self.done_tasks()
        stale = [t for t in pending if self.is_stale(t)]

        self.stats_label.setText(
            f"待办 {len(pending)} · 已完成 {len(done)}"
            + (f" · ⚠ 旧任务 {len(stale)}" if stale else ""))

        if self._page == "pending":
            if stale:
                self.banner.setText(
                    f"⏰ 有 {len(stale)} 个任务超过 {STALE_DAYS} 天没完成了,优先处理一下吧!")
                self.banner.show()
            else:
                self.banner.hide()
            items = [(t, False) for t in pending]
            empty_msg = "🎈 没有待办任务,享受这一刻的轻松!"
        else:
            self.banner.hide()
            items = [(t, True) for t in done]
            empty_msg = "还没有完成的任务,去待办页划掉第一条吧 💪"

        if not items:
            lab = QLabel(empty_msg)
            lab.setStyleSheet("color: #5c6474; font-size: 14px;")
            lab.setAlignment(Qt.AlignCenter)
            lab.setFixedHeight(80)
            self.list_lay.insertWidget(self.list_lay.count() - 1, lab)
            return

        for t, is_done in items:
            row = TaskRow(t, is_done, self.is_stale(t), self.days_old(t),
                          self._on_complete, self._on_delete, self._on_restore)
            self.list_lay.insertWidget(self.list_lay.count() - 1, row)

    # ---- 鼓励 toast ----
    def _show_toast(self, msg: str):
        if self._toast_widget is not None:
            self._toast_widget.deleteLater()
            self._toast_widget = None
        top = self.entry.window()
        t = QLabel(msg, top)
        t.setStyleSheet("""
            QLabel {
                background: #27402e; color: #bfe8c8; border: 1px solid #35563e;
                border-radius: 12px; padding: 12px 22px;
                font-size: 15px; font-weight: bold;
            }
        """)
        t.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        t.adjustSize()
        t.move((top.width() - t.width()) // 2, int(top.height() * 0.18))
        t.show()
        t.raise_()
        self._toast_widget = t
        QTimer.singleShot(2800, self._fade_toast)

    def _fade_toast(self):
        t = self._toast_widget
        if t is None:
            return
        self._toast_widget = None
        t.deleteLater()

    def on_close(self):
        self._save()
        self.log.info("daily tasks closed, %d tasks", len(self.tasks))
