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
import tkinter as tk

try:
    import customtkinter as ctk
    HAS_CTK = True
except ImportError:
    HAS_CTK = False

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
    def build(self, root: tk.Misc) -> None:
        self.tasks = self._load()
        self._toast_id = None
        self._page = "pending"

        self.wrap = self._frame(root, transparent=True)
        self.wrap.pack(fill="both", expand=True, padx=8, pady=6)

        # 顶部:添加 + 页面切换
        top = self._frame(self.wrap, transparent=True)
        top.pack(fill="x", pady=(0, 10))

        self.entry_var = tk.StringVar()
        self.entry = (ctk.CTkEntry(top, textvariable=self.entry_var, height=38,
                                   corner_radius=9, placeholder_text="✏️ 输入任务,回车快速添加…",
                                   font=ctk.CTkFont(size=14))
                      if HAS_CTK else tk.Entry(top, textvariable=self.entry_var, font=("", 13)))
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry.bind("<Return>", lambda _e: self._on_add())
        self._btn(top, "＋ 添加", self._on_add, width=90).pack(side="left", padx=(0, 8))
        self.pending_btn = self._btn(top, "📋 待办", lambda: self._switch("pending"), width=80)
        self.pending_btn.pack(side="left", padx=(0, 4))
        self.done_btn = self._btn(top, "✅ 已完成", lambda: self._switch("done"), width=90)
        self.done_btn.pack(side="left")

        # 统计条
        self.stats_label = self._label(self.wrap, "", 12, "#8a93a6")
        self.stats_label.pack(anchor="w", pady=(0, 6))

        # 列表(滚动)
        if HAS_CTK:
            self.list_frame = ctk.CTkScrollableFrame(self.wrap, fg_color="transparent")
        else:
            outer = tk.Frame(self.wrap)
            cv = tk.Canvas(outer, highlightthickness=0)
            self.list_frame = tk.Frame(cv)
            sb = tk.Scrollbar(outer, orient="vertical", command=cv.yview)
            cv.configure(yscrollcommand=sb.set)
            cv.create_window((0, 0), window=self.list_frame, anchor="nw")
            self.list_frame.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
            cv.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
            outer.pack(fill="both", expand=True)
        if HAS_CTK:
            self.list_frame.pack(fill="both", expand=True)

        # 提醒横幅
        self.banner = self._label(self.wrap, "", 13, "#e8a54b")

        self._render()

    # ---- 控件工厂 ----
    def _frame(self, parent, transparent=False, radius=0, fg=None):
        if HAS_CTK:
            kw = {"corner_radius": radius}
            kw["fg_color"] = "transparent" if transparent else (fg or "#1e222c")
            return ctk.CTkFrame(parent, **kw)
        return tk.Frame(parent)

    def _label(self, parent, text, size=13, color=None):
        if HAS_CTK:
            kw = {"font": ctk.CTkFont(size=size)}
            if color:
                kw["text_color"] = color
            return ctk.CTkLabel(parent, text=text, **kw)
        return tk.Label(parent, text=text, anchor="w", justify="left")

    def _btn(self, parent, text, cmd, width=None, fg=None, hover=None):
        if HAS_CTK:
            kw = {"command": cmd, "corner_radius": 8}
            if width: kw["width"] = width
            if fg: kw["fg_color"] = fg
            if hover: kw["hover_color"] = hover
            return ctk.CTkButton(parent, text=text, **kw)
        return tk.Button(parent, text=text, command=cmd)

    # ---- 交互 ----
    def _switch(self, page: str):
        self._page = page
        hl = "#4f8cff" if HAS_CTK else None
        dim = "#2a2f3a"
        if HAS_CTK:
            self.pending_btn.configure(fg_color=hl if page == "pending" else dim)
            self.done_btn.configure(fg_color=hl if page == "done" else dim)
        self._render()

    def _on_add(self):
        title = self.entry_var.get().strip()
        if not title:
            return
        self.add_task(title)
        self.entry_var.set("")
        self._page = "pending"
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
        for w in self.list_frame.winfo_children():
            w.destroy()

        pending = self.pending_tasks()
        done = self.done_tasks()
        stale = [t for t in pending if self.is_stale(t)]

        self._set_text(self.stats_label,
                       f"待办 {len(pending)} · 已完成 {len(done)}"
                       + (f" · ⚠ 旧任务 {len(stale)}" if stale else ""))

        if self._page == "pending":
            if stale:
                self.banner.pack(anchor="w", pady=(0, 6)) if not self.banner.winfo_manager() else None
                self._set_text(self.banner,
                               f"⏰ 有 {len(stale)} 个任务超过 {STALE_DAYS} 天没完成了,优先处理一下吧!")
            else:
                self.banner.pack_forget()
            if not pending:
                self._empty("🎈 没有待办任务,享受这一刻的轻松!")
                return
            for t in pending:
                self._task_row(t, done=False)
        else:
            self.banner.pack_forget()
            if not done:
                self._empty("还没有完成的任务,去待办页划掉第一条吧 💪")
                return
            for t in done:
                self._task_row(t, done=True)

    def _empty(self, text: str):
        lb = self._label(self.list_frame, text, 14, "#5c6474")
        lb.pack(pady=40)

    def _task_row(self, t: dict, done: bool):
        stale = self.is_stale(t)
        if HAS_CTK:
            row = ctk.CTkFrame(self.list_frame, corner_radius=10,
                               fg_color="#232833" if not stale else "#2e2618",
                               border_width=1,
                               border_color="#e8a54b" if stale else "#2a2f3a")
        else:
            row = tk.Frame(self.list_frame, bg="#232833")
        row.pack(fill="x", pady=3)

        age = f" · {self.days_old(t)}天前添加" if stale else ""
        if done:
            when = time.strftime("%m-%d %H:%M", time.localtime(t["done_at"]))
            text = f"✔ {t['title']}"
            sub = f"完成于 {when}"
            color = "#5c6474"
        else:
            text = ("⚠ " if stale else "") + t["title"]
            sub = f"{time.strftime('%m-%d %H:%M', time.localtime(t['created']))} 创建{age}"
            color = "#e8a54b" if stale else "#e6e9ef"

        main_lb = self._label(row, text, 14, color)
        main_lb.pack(anchor="w", padx=14, pady=(8, 0))
        sub_lb = self._label(row, sub, 11, "#6a7385")
        sub_lb.pack(anchor="w", padx=14, pady=(0, 8))

        if not done:
            # 点标题即完成
            for w in (main_lb, sub_lb):
                w.bind("<Button-1>", lambda _e, tid=t["id"]: self._on_complete(tid))
                if HAS_CTK:
                    w.configure(cursor="hand2")
            self._btn(row, "🗑", lambda tid=t["id"]: self._on_delete(tid),
                      width=40, fg="#3a2730", hover="#54353f").pack(side="right", padx=8, pady=8)
            self._btn(row, "✔ 完成", lambda tid=t["id"]: self._on_complete(tid),
                      width=76, fg="#27402e", hover="#35563e").pack(side="right", padx=(0, 4))
        else:
            self._btn(row, "🗑", lambda tid=t["id"]: self._on_delete(tid),
                      width=40, fg="#3a2730", hover="#54353f").pack(side="right", padx=8, pady=8)
            self._btn(row, "↩ 还原", lambda tid=t["id"]: self._on_restore(tid),
                      width=76, fg="#2a2f3a", hover="#3a4150").pack(side="right", padx=(0, 4))

    def _set_text(self, widget, text):
        if HAS_CTK:
            widget.configure(text=text)
        else:
            widget.config(text=text)

    # ---- 鼓励 toast ----
    def _show_toast(self, msg: str):
        if self._toast_id:
            try:
                self._toast_id.destroy()
            except Exception:
                pass
        top = self.wrap.winfo_toplevel()
        if HAS_CTK:
            t = ctk.CTkLabel(top, text=msg, corner_radius=12, fg_color="#27402e",
                             text_color="#bfe8c8", font=ctk.CTkFont(size=15, weight="bold"),
                             padx=22, pady=12, border_width=1, border_color="#35563e")
        else:
            t = tk.Label(top, text=msg, bg="#27402e", fg="#bfe8c8", padx=22, pady=12)
        t.place(relx=0.5, rely=0.18, anchor="n")
        self._toast_id = t
        t.after(2800, self._fade_toast)

    def _fade_toast(self):
        t = self._toast_id
        if t is None:
            return
        self._toast_id = None
        try:
            t.destroy()
        except Exception:
            pass

    def on_close(self):
        self._save()
        self.log.info("daily tasks closed, %d tasks", len(self.tasks))
