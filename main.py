"""
Toolbox 主程序 —— 现代化图形界面 (CustomTkinter)。

布局:
┌──────────┬─────────────────────────────────┐
│ 侧边栏    │  🔍 搜索栏(关键字 + 自然语言)   │
│ · 首页    │  ┌────┐ ┌────┐ ┌────┐          │
│ · 分类    │  │工具卡│ │工具卡│ │工具卡│  …      │
│ · 环境    │  └────┘ └────┘ └────┘          │
│          │  (点击卡片 → 右侧/全屏运行工具)   │
└──────────┴─────────────────────────────────┘

Windows 运行:  python main.py
"""
from __future__ import annotations

import os
import sys
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

try:
    import customtkinter as ctk
    HAS_CTK = True
except ImportError:
    HAS_CTK = False

from core import EnvManager, Registry, SearchEngine, Manifest, human_size
from core.env_manager import default_root as main_env_default_root

ACCENT = "#4f8cff"

# ---- 内置工具清单(先注册占位,后续逐个实现)----
BUILTIN_APPS: list[dict] = [
    {
        "id": "demo_notepad",
        "name": "便签",
        "version": "0.1.0",
        "description": "一个简单的记事本,演示工具如何接入工具箱:数据受环境管理,自动保存到应用专属目录。",
        "module": "apps.demo_notepad",
        "class_name": "NotepadApp",
        "category": "效率",
        "icon": "📝",
        "keywords": ["记事", "笔记", "notepad", "note", "记录"],
    },
    {
        "id": "audio_player",
        "name": "音频播放器",
        "version": "0.1.0",
        "description": "播放 WAV 和 PCM 裸数据音频,可拖动进度条,可设置采样率、位深、通道数,带波形显示。",
        "module": "apps.audio_player",
        "class_name": "AudioPlayerApp",
        "category": "音视频",
        "icon": "🎵",
        "keywords": ["音频", "播放", "wav", "pcm", "声音", "audio", "采样率", "波形"],
    },
    {
        "id": "daily_tasks",
        "name": "每日任务",
        "version": "0.1.0",
        "description": "每日待办清单:快速添加删除任务,点击完成有鼓励语,旧任务提醒,已完成任务可归档查看。",
        "module": "apps.daily_tasks",
        "class_name": "DailyTasksApp",
        "category": "效率",
        "icon": "✅",
        "keywords": ["任务", "待办", "todo", "打卡", "清单", "提醒", "每日"],
    },
    # ↓ 未来工具在这里追加 manifest 即可,无需改界面代码
]


def seed_registry(reg: Registry) -> dict:
    """注册内置工具 + 同步外部插件。返回插件扫描结果(含 errors)。"""
    existing = {m.id for m in reg.all()}
    for d in BUILTIN_APPS:
        if d["id"] not in existing:
            try:
                reg.register(Manifest.from_dict(d))
            except Exception as e:
                print(f"[warn] 注册 {d['id']} 失败: {e}")
    return reg.sync_plugins()


# 插件模板(「生成插件模板」按钮写入插件目录,新手照着改即可)
PLUGIN_TEMPLATE = '''# -*- coding: utf-8 -*-
"""Toolbox 插件示例:掷骰子。复制此文件到插件目录,改成你自己的工具。"""
import random
import tkinter as tk
import customtkinter as ctk

# ① 元数据:id 全局唯一(小写字母/数字/下划线),description 写清楚功能(搜索靠它)
MANIFEST = {
    "id": "hello_dice",
    "name": "掷骰子",
    "version": "1.0.0",
    "description": "示例插件:点击按钮随机掷骰子,演示如何开发 Toolbox 第三方工具。",
    "category": "示例",
    "icon": "🎲",
    "keywords": ["骰子", "随机", "示例", "dice"],
    "class_name": "HelloPlugin",
}

# ② 工具类:必须继承 ToolApp。打包环境下用 try 导入兜底。
try:
    from core.base_app import ToolApp
except ImportError:  # 开发调试时
    class ToolApp:
        def __init__(self, manifest, env):
            self.manifest, self.env = manifest, env

class HelloPlugin(ToolApp):
    def build(self, root):
        """root 是你的界面容器,随意布局。"""
        frame = ctk.CTkFrame(root, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=16, pady=16)

        self.result = ctk.CTkLabel(frame, text="🎲", font=ctk.CTkFont(size=64))
        self.result.pack(pady=20)

        # ③ 数据存取:一律走 self.env(受管沙箱),别写死路径
        cfg = self.env.get_config({"rolls": 0})
        self.count = ctk.CTkLabel(frame, text=f"历史掷骰 {cfg.get(\'rolls\', 0)} 次",
                                  text_color="#8a93a6")
        self.count.pack()

        def roll():
            n = random.randint(1, 6)
            self.result.configure(text=["⚀","⚁","⚂","⚃","⚄","⚅"][n-1])
            cfg["rolls"] = cfg.get("rolls", 0) + 1
            self.env.save_config(cfg)
            self.count.configure(text=f"历史掷骰 {cfg[\'rolls\']} 次")

        ctk.CTkButton(frame, text="掷!", width=120, height=38, command=roll).pack(pady=12)

    def on_close(self):
        """可选:窗口关闭时清理/保存。"""
        pass
'''


if HAS_CTK:
    class ToolboxApp(ctk.CTk):
        def __init__(self):
            super().__init__()
            ctk.set_appearance_mode("dark")
            ctk.set_default_color_theme("blue")
            self.title("Toolbox 工具箱")
            self.geometry("1080x680")
            self.minsize(860, 540)

            self.env = EnvManager.instance()
            self.registry = Registry(self.env)
            self._plugin_report = seed_registry(self.registry)
            self.search_engine = SearchEngine(self.registry.all())
            self._arrange_mode = False

            self._build_layout()
            self._show_home()

        # ---------- 布局 ----------
        def _build_layout(self):
            self.grid_columnconfigure(1, weight=1)
            self.grid_rowconfigure(0, weight=1)

            # 侧边栏
            self.sidebar = ctk.CTkFrame(self, width=190, corner_radius=0,
                                        fg_color="#1a1d24")
            self.sidebar.grid(row=0, column=0, sticky="nsw")
            self.sidebar.grid_propagate(False)

            ctk.CTkLabel(self.sidebar, text="🧰 Toolbox",
                         font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(24, 4), padx=16, anchor="w")
            ctk.CTkLabel(self.sidebar, text="受管 · 可搜索 · 可扩展",
                         font=ctk.CTkFont(size=11), text_color="#8a93a6").pack(padx=16, anchor="w")

            self.nav_buttons: list[ctk.CTkButton] = []
            self.sidebar_items = ctk.CTkFrame(self.sidebar, fg_color="transparent")
            self.sidebar_items.pack(fill="both", expand=True)
            self._rebuild_sidebar()

            # 主区域
            self.main = ctk.CTkFrame(self, corner_radius=0, fg_color="#12141a")
            self.main.grid(row=0, column=1, sticky="nsew")
            self.main.grid_rowconfigure(1, weight=1)
            self.main.grid_columnconfigure(0, weight=1)

            # 搜索栏
            top = ctk.CTkFrame(self.main, fg_color="transparent")
            top.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 8))
            top.grid_columnconfigure(0, weight=1)

            self.search_var = tk.StringVar()
            self.search_var.trace_add("write", lambda *_: self._on_search())
            self.search_entry = ctk.CTkEntry(
                top, textvariable=self.search_var, height=40, corner_radius=10,
                placeholder_text="🔍  搜索工具:输入关键字,或用自然语言描述,如「能把图片压小一点的」",
                font=ctk.CTkFont(size=14))
            self.search_entry.grid(row=0, column=0, sticky="ew")

            # 内容区
            self.content = ctk.CTkFrame(self.main, fg_color="transparent")
            self.content.grid(row=1, column=0, sticky="nsew", padx=20, pady=(4, 16))
            self.content.grid_rowconfigure(0, weight=1)
            self.content.grid_columnconfigure(0, weight=1)

            # 运行中工具容器
            self.tool_host = ctk.CTkFrame(self.main, fg_color="transparent")

        def _rebuild_sidebar(self):
            """重建侧边栏导航(分类变化后调用,如安装/卸载插件)。"""
            for w in self.sidebar_items.winfo_children():
                w.destroy()
            self.nav_buttons = []
            self._nav_button("🏠  首页", self._show_home)

            cats = self.registry.categories()
            if cats:
                ctk.CTkLabel(self.sidebar_items, text="分类", font=ctk.CTkFont(size=12, weight="bold"),
                             text_color="#8a93a6").pack(pady=(20, 4), padx=16, anchor="w")
                for c in cats:
                    self._nav_button(f"▸  {c}", lambda cc=c: self._show_home(category=cc))

            ctk.CTkLabel(self.sidebar_items, text="系统", font=ctk.CTkFont(size=12, weight="bold"),
                         text_color="#8a93a6").pack(pady=(20, 4), padx=16, anchor="w")
            self._nav_button("🧩  插件管理", self._show_plugins_page)
            self._nav_button("🗂  环境管理", self._show_env_page)

        def _nav_button(self, text: str, command) -> ctk.CTkButton:
            btn = ctk.CTkButton(self.sidebar_items, text=text, anchor="w", height=36,
                                corner_radius=8, fg_color="transparent",
                                hover_color="#2a2f3a", font=ctk.CTkFont(size=14),
                                command=command)
            btn.pack(fill="x", padx=10, pady=2)
            self.nav_buttons.append(btn)
            return btn

        # ---------- 页面 ----------
        def _clear_content(self):
            for w in self.content.winfo_children():
                w.destroy()
            self.tool_host.grid_forget()
            for w in self.tool_host.winfo_children():
                w.destroy()
            # 关键:用完整 grid 参数重新布局,否则会丢 row/sticky/pad 导致黑屏错位
            self.content.grid(row=1, column=0, sticky="nsew", padx=20, pady=(4, 16))

        def _show_home(self, category: str | None = None):
            # 先抑制 trace:清空搜索框会触发 _on_search,导致重复渲染(叠影/花屏)
            self._suppress_search = True
            self.search_var.set("")
            self._suppress_search = False
            self._clear_content()
            apps = self.registry.all()
            if category:
                apps = [m for m in apps if m.category == category]
            title = f"全部工具 · {category}" if category else "全部工具"
            self._render_cards(title, apps)

        def _on_search(self):
            if getattr(self, "_suppress_search", False):
                return
            q = self.search_var.get()
            self._clear_content()
            if not q.strip():
                self._render_cards("全部工具", self.registry.all())
                return
            results = self.search_engine.search(q)
            if results:
                self._render_cards(f"「{q}」的搜索结果 · {len(results)} 项",
                                   [r.manifest for r in results],
                                   reasons={r.manifest.id: r.reason for r in results})
            else:
                ctk.CTkLabel(self.content, text=f"😕 没有找到与「{q}」相关的工具\n试试换个说法?",
                             font=ctk.CTkFont(size=16), text_color="#8a93a6").grid(pady=60)

        def _render_cards(self, title: str, apps: list[Manifest], reasons: dict | None = None):
            header = ctk.CTkFrame(self.content, fg_color="transparent")
            header.grid(row=0, column=0, sticky="ew", columnspan=4, pady=(0, 10))
            ctk.CTkLabel(header, text=title, anchor="w",
                         font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
            if self._arrange_mode:
                ctk.CTkButton(header, text="✔ 完成排版", width=110,
                              fg_color="#27402e", hover_color="#35563e",
                              command=self._toggle_arrange).pack(side="right")
                ctk.CTkLabel(header, text="用 ← → 调整工具位置,顺序自动保存",
                             font=ctk.CTkFont(size=12),
                             text_color="#8a93a6").pack(side="right", padx=12)
            else:
                ctk.CTkButton(header, text="↕ 排版", width=70, fg_color="#2a2f3a",
                              hover_color="#3a4150",
                              command=self._toggle_arrange).pack(side="right")

            grid = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
            grid.grid(row=1, column=0, sticky="nsew", columnspan=4)
            self.content.grid_rowconfigure(1, weight=1)
            for i in range(4):
                grid.grid_columnconfigure(i, weight=1, uniform="card")

            for idx, m in enumerate(apps):
                r, c = divmod(idx, 4)
                self._tool_card(grid, m, r, c, (reasons or {}).get(m.id, ""),
                                arrangeable=not reasons)

            if not apps:
                ctk.CTkLabel(grid, text="暂无工具。点侧边栏「🧩 插件管理」安装第三方工具,\n或在 main.py 的 BUILTIN_APPS 中注册内置工具。",
                             text_color="#8a93a6").grid(row=0, column=0, columnspan=4, pady=40)

        def _toggle_arrange(self):
            self._arrange_mode = not self._arrange_mode
            self._suppress_search = True
            q = self.search_var.get()
            self._suppress_search = False
            if q.strip():
                self._on_search()
            else:
                self._show_home()

        def _move_app(self, app_id: str, delta: int):
            if self.registry.move_app(app_id, delta):
                self.search_engine.update(self.registry.all())
                self._suppress_search = True
                q = self.search_var.get()
                self._suppress_search = False
                if q.strip():
                    self._on_search()
                else:
                    self._show_home()

        def _tool_card(self, parent, m: Manifest, row: int, col: int, reason: str,
                       arrangeable: bool = False):
            CARD_BG, CARD_HOVER = "#1e222c", "#252b38"
            card = ctk.CTkFrame(parent, corner_radius=14, fg_color=CARD_BG,
                                border_width=1,
                                border_color="#4f8cff" if self._arrange_mode else "#2a2f3a")
            card.grid(row=row, column=col, sticky="nsew", padx=8, pady=8)

            # 手动实现悬停高亮(CTkFrame 不支持 hover_color)
            def _hover_on(_e):
                card.configure(fg_color=CARD_HOVER)
            def _hover_off(_e):
                card.configure(fg_color=CARD_BG)

            # 排版模式的移动按钮子树:不能被 _wire 重复绑定点击
            # (否则点「右移」会同时触发 command(+1) 和 card 的 Button-1 绑定(-1),净移动为0)
            self._arrange_btn_zone = None

            def _wire(w):
                if w is self._arrange_btn_zone:
                    return  # 跳过移动按钮区域,由按钮自己的 command 处理
                if self._arrange_mode and arrangeable:
                    w.bind("<Button-1>", lambda _e, mid=m.id: self._move_app(mid, -1))
                    w.bind("<Button-3>", lambda _e, mid=m.id: self._move_app(mid, 1))
                else:
                    w.bind("<Button-1>", lambda _e, mid=m.id: self._launch(mid))
                w.bind("<Enter>", _hover_on, add="+")
                w.bind("<Leave>", _hover_off, add="+")
                for c in w.winfo_children():
                    _wire(c)

            ctk.CTkLabel(card, text=m.icon, font=ctk.CTkFont(size=30)).pack(anchor="w", padx=16, pady=(14, 2))
            ctk.CTkLabel(card, text=m.name, font=ctk.CTkFont(size=15, weight="bold"),
                         anchor="w").pack(anchor="w", padx=16)
            ctk.CTkLabel(card, text=m.category + ("  · 插件" if m.source == "plugin" else ""),
                         font=ctk.CTkFont(size=11),
                         text_color=ACCENT, anchor="w").pack(anchor="w", padx=16)
            desc = m.description if len(m.description) <= 46 else m.description[:45] + "…"
            ctk.CTkLabel(card, text=desc, font=ctk.CTkFont(size=12),
                         text_color="#9aa3b5", anchor="w", justify="left",
                         wraplength=170).pack(anchor="w", padx=16, pady=(6, 4))
            if self._arrange_mode and arrangeable:
                mv = ctk.CTkFrame(card, fg_color="transparent")
                mv.pack(anchor="w", padx=16, pady=(0, 10))
                self._arrange_btn_zone = mv
                ctk.CTkButton(mv, text="← 左移", width=70, height=26,
                              command=lambda mid=m.id: self._move_app(mid, -1)).pack(side="left", padx=(0, 6))
                ctk.CTkButton(mv, text="右移 →", width=70, height=26,
                              command=lambda mid=m.id: self._move_app(mid, 1)).pack(side="left")
            elif reason:
                ctk.CTkLabel(card, text=f"✓ {reason}", font=ctk.CTkFont(size=10),
                             text_color="#5cbf7a", anchor="w").pack(anchor="w", padx=16, pady=(0, 10))
            else:
                ctk.CTkLabel(card, text=f"v{m.version}", font=ctk.CTkFont(size=10),
                             text_color="#5c6474", anchor="w").pack(anchor="w", padx=16, pady=(0, 10))

            _wire(card)  # 所有子控件创建完成后再统一绑定

        def _launch(self, app_id: str):
            try:
                app = self.registry.launch(app_id)
            except Exception as e:
                self._toast(f"启动失败: {e}")
                return
            self._clear_content()
            self.content.grid_forget()
            self.tool_host.grid(row=1, column=0, sticky="nsew", padx=8, pady=(4, 8))

            bar = ctk.CTkFrame(self.tool_host, fg_color="transparent")
            bar.pack(fill="x", padx=8, pady=(4, 6))
            m = app.manifest
            ctk.CTkLabel(bar, text=f"{m.icon} {m.name}", font=ctk.CTkFont(size=15, weight="bold")).pack(side="left")
            ctk.CTkButton(bar, text="← 返回", width=80, fg_color="#2a2f3a",
                          hover_color="#3a4150", command=self._show_home).pack(side="right")

            body = ctk.CTkFrame(self.tool_host, fg_color="transparent")
            body.pack(fill="both", expand=True)
            app.build(body)
            self._current_app = app

        # ---------- 插件管理页 ----------
        def _show_plugins_page(self):
            self._clear_content()
            ctk.CTkLabel(self.content, text="🧩 插件管理", anchor="w",
                         font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, sticky="ew", columnspan=2)

            intro = ctk.CTkFrame(self.content, corner_radius=12, fg_color="#1e222c")
            intro.grid(row=1, column=0, sticky="ew", columnspan=2, pady=10)
            ctk.CTkLabel(intro, anchor="w", justify="left", text_color="#9aa3b5",
                         font=ctk.CTkFont(size=12),
                         text=("安装第三方工具:把插件 .py 文件放进插件目录,点「扫描安装」即可。\n"
                               f"插件目录:{self.registry.plugins_dir}\n"
                               "开发文档:仓库 docs/PLUGIN_GUIDE.md")).pack(padx=16, pady=12, anchor="w")

            btns = ctk.CTkFrame(self.content, fg_color="transparent")
            btns.grid(row=2, column=0, sticky="w", columnspan=2, pady=(0, 10))
            ctk.CTkButton(btns, text="📂 打开插件目录", width=140,
                          command=self._open_plugins_dir).pack(side="left", padx=(0, 8))
            ctk.CTkButton(btns, text="🔄 扫描安装", width=110,
                          command=self._rescan_plugins).pack(side="left", padx=(0, 8))
            ctk.CTkButton(btns, text="📄 生成插件模板", width=130, fg_color="#2a2f3a",
                          hover_color="#3a4150",
                          command=self._make_plugin_template).pack(side="left")

            # 上次扫描报告
            rep = self._plugin_report
            msgs = []
            if rep.get("added"):   msgs.append("新装: " + ", ".join(rep["added"]))
            if rep.get("updated"): msgs.append("更新: " + ", ".join(rep["updated"]))
            if rep.get("removed"): msgs.append("已移除: " + ", ".join(rep["removed"]))
            if rep.get("errors"):  msgs.append("⚠ " + " | ".join(rep["errors"]))
            if msgs:
                ctk.CTkLabel(self.content, text="  ".join(msgs), anchor="w",
                             font=ctk.CTkFont(size=12), text_color="#e8a54b").grid(
                    row=3, column=0, sticky="ew", columnspan=2, pady=(0, 6))

            # 已安装插件列表
            plugins = [m for m in self.registry.all() if m.source == "plugin"]
            table = ctk.CTkFrame(self.content, corner_radius=12, fg_color="#1e222c")
            table.grid(row=4, column=0, sticky="nsew", columnspan=2)
            self.content.grid_rowconfigure(4, weight=1)
            if not plugins:
                ctk.CTkLabel(table, text="尚未安装任何插件",
                             text_color="#5c6474").pack(pady=30)
            else:
                for i, m in enumerate(plugins):
                    row = ctk.CTkFrame(table, fg_color="transparent")
                    row.pack(fill="x", padx=14, pady=4)
                    ctk.CTkLabel(row, text=f"{m.icon} {m.name}",
                                 font=ctk.CTkFont(size=13, weight="bold"),
                                 width=140, anchor="w").pack(side="left")
                    ctk.CTkLabel(row, text=f"v{m.version} · {m.category}",
                                 text_color="#8a93a6", width=110, anchor="w").pack(side="left")
                    ctk.CTkLabel(row, text=m.path, text_color="#5c6474",
                                 font=ctk.CTkFont(size=10), anchor="w").pack(side="left", fill="x", expand=True)
                    ctk.CTkButton(row, text="卸载", width=60, height=26,
                                  fg_color="#5a2730", hover_color="#7a3540",
                                  command=lambda mm=m: self._uninstall_plugin(mm)).pack(side="right")

        def _open_plugins_dir(self):
            import subprocess
            d = str(self.registry.plugins_dir)
            if sys.platform == "win32":
                os.startfile(d)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", d])
            else:
                subprocess.Popen(["xdg-open", d])

        def _rescan_plugins(self):
            self._plugin_report = self.registry.sync_plugins()
            self.search_engine.update(self.registry.all())
            self._rebuild_sidebar()
            self._show_plugins_page()
            added, errs = self._plugin_report["added"], self._plugin_report["errors"]
            if added:
                self._toast(f"✅ 已安装 {len(added)} 个插件: {', '.join(added)}")
            elif errs:
                self._toast("⚠ 部分插件加载失败,详见页面提示")

        def _make_plugin_template(self):
            """在插件目录生成一个可直接运行的示例插件,方便照着改。"""
            target = self.registry.plugins_dir / "hello_plugin.py"
            if target.exists():
                self._toast("模板已存在: hello_plugin.py")
                self._open_plugins_dir()
                return
            target.write_text(PLUGIN_TEMPLATE, "utf-8")
            self._toast("已生成模板 hello_plugin.py,点「扫描安装」试试")

        def _uninstall_plugin(self, m: Manifest):
            from tkinter import messagebox
            if not messagebox.askyesno("卸载插件",
                                       f"卸载「{m.name}」?\n将从注册表移除。插件文件和数据目录保留,\n"
                                       f"如要彻底删除,请手动删文件和在环境管理页删数据。"):
                return
            self.registry.unregister(m.id)
            self.search_engine.update(self.registry.all())
            self._rebuild_sidebar()
            self._show_plugins_page()
            self._toast(f"已卸载 {m.name}")

        def _show_env_page(self):
            self._clear_content()
            ctk.CTkLabel(self.content, text="🗂 环境管理", anchor="w",
                         font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, sticky="ew", columnspan=2)

            info = ctk.CTkFrame(self.content, corner_radius=12, fg_color="#1e222c")
            info.grid(row=1, column=0, sticky="nsew", columnspan=2, pady=10)
            rows = [
                ("数据根目录", str(self.env.root)),
                ("注册表", str(self.env.file if hasattr(self.env, 'file') else self.registry.file)),
                ("已注册 App", f"{len(self.registry.all())} 个"),
                ("磁盘占用", human_size(self.env.total_usage_bytes())),
            ]
            for i, (k, v) in enumerate(rows):
                ctk.CTkLabel(info, text=k, text_color="#8a93a6", anchor="w").grid(row=i, column=0, sticky="w", padx=16, pady=6)
                ctk.CTkLabel(info, text=v, anchor="w", font=ctk.CTkFont(size=12)).grid(row=i, column=1, sticky="w", padx=8, pady=6)
            info.grid_columnconfigure(1, weight=1)

            # 更改数据目录
            chg = ctk.CTkFrame(info, fg_color="transparent")
            chg.grid(row=len(rows), column=0, columnspan=2, sticky="w", padx=10, pady=(4, 10))
            ctk.CTkButton(chg, text="📁 更改数据目录…", width=150,
                          command=self._change_data_root).pack(side="left", padx=6)
            ctk.CTkButton(chg, text="恢复默认位置", width=110, fg_color="#2a2f3a",
                          hover_color="#3a4150",
                          command=lambda: self._apply_new_root(main_env_default_root())).pack(side="left", padx=6)
            ctk.CTkLabel(chg, text="更改后旧数据自动搬迁(可跨盘)", font=ctk.CTkFont(size=11),
                         text_color="#5c6474").pack(side="left", padx=10)

            table = ctk.CTkFrame(self.content, corner_radius=12, fg_color="#1e222c")
            table.grid(row=2, column=0, sticky="nsew", columnspan=2)
            self.content.grid_rowconfigure(2, weight=1)
            heads = ("App", "数据目录", "占用", "操作")
            for c, h in enumerate(heads):
                ctk.CTkLabel(table, text=h, font=ctk.CTkFont(size=13, weight="bold"),
                             text_color="#8a93a6").grid(row=0, column=c, sticky="w", padx=14, pady=(12, 6))
            for r, m in enumerate(self.registry.all(), start=1):
                appenv = self.env.environment_for(m.id)
                ctk.CTkLabel(table, text=f"{m.icon} {m.name}").grid(row=r, column=0, sticky="w", padx=14, pady=4)
                ctk.CTkLabel(table, text=str(appenv.base), text_color="#9aa3b5",
                             font=ctk.CTkFont(size=11)).grid(row=r, column=1, sticky="w", padx=14)
                ctk.CTkLabel(table, text=human_size(appenv.usage_bytes())).grid(row=r, column=2, sticky="w", padx=14)
                btns = ctk.CTkFrame(table, fg_color="transparent")
                btns.grid(row=r, column=3, sticky="w", padx=14)
                ctk.CTkButton(btns, text="清缓存", width=70, height=26, fg_color="#2a2f3a",
                              hover_color="#3a4150",
                              command=lambda a=m.id: self._clear_cache(a)).pack(side="left", padx=3)
                ctk.CTkButton(btns, text="删数据", width=70, height=26, fg_color="#5a2730",
                              hover_color="#7a3540",
                              command=lambda a=m.id: self._remove_data(a)).pack(side="left", padx=3)

        def _clear_cache(self, app_id: str):
            freed = self.env.environment_for(app_id).clear_cache()
            self._toast(f"{app_id} 缓存已清理,释放 {human_size(freed)}")
            self._show_env_page()

        # ---------- 更改数据目录 ----------
        def _change_data_root(self):
            from tkinter import filedialog, messagebox
            path = filedialog.askdirectory(title="选择新的数据目录",
                                           initialdir=str(self.env.root.parent))
            if not path:
                return
            if not messagebox.askyesno("确认更改",
                                       f"数据目录将更改为:\n{path}\n\n旧数据会自动搬迁过去,继续吗?"):
                return
            self._apply_new_root(path)

        def _apply_new_root(self, new_root):
            from pathlib import Path
            try:
                self.env.change_root(new_root)
            except OSError as e:
                self._toast(f"❌ {e}")
                return
            # 重建注册表与搜索引擎(指向新 root)
            self.registry = Registry(self.env)
            self._plugin_report = seed_registry(self.registry)
            self.search_engine.update(self.registry.all())
            self._rebuild_sidebar()
            self._toast(f"✅ 数据目录已更改为 {Path(new_root)}")
            self._show_env_page()

        def _remove_data(self, app_id: str):
            from tkinter import messagebox
            if messagebox.askyesno("确认", f"彻底删除 {app_id} 的所有数据?\n(注册信息保留,数据不可恢复)"):
                self.env.remove_app_data(app_id)
                self._show_env_page()

        def _toast(self, msg: str):
            t = ctk.CTkLabel(self, text=msg, corner_radius=8, fg_color="#2a2f3a",
                             font=ctk.CTkFont(size=13), padx=14, pady=8)
            t.place(relx=0.5, y=self.winfo_height() - 60, anchor="s")
            t.after(2600, t.destroy)

        def destroy(self):
            app = getattr(self, "_current_app", None)
            if app:
                try:
                    app.on_close()
                except Exception:
                    pass
            super().destroy()
else:
    # 无 customtkinter 时的极简降级界面(保证可用)
    class ToolboxApp(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("Toolbox 工具箱 (基础模式: pip install customtkinter 获得现代界面)")
            self.geometry("760x520")
            self.env = EnvManager.instance()
            self.registry = Registry(self.env)
            seed_registry(self.registry)
            self.search_engine = SearchEngine(self.registry.all())

            self.search_var = tk.StringVar()
            tk.Entry(self, textvariable=self.search_var, width=60).pack(padx=12, pady=10, fill="x")
            self.search_var.trace_add("write", lambda *_: self.refresh())
            self.list = tk.Listbox(self, font=("Microsoft YaHei UI", 12))
            self.list.pack(fill="both", expand=True, padx=12, pady=(0, 12))
            self.list.bind("<Double-1>", lambda _e: self.launch())
            self.refresh()

        def refresh(self):
            self.list.delete(0, "end")
            q = self.search_var.get()
            results = self.search_engine.search(q) if q.strip() else \
                [type("R", (), {"manifest": m})() for m in self.registry.all()]
            for r in results:
                m = r.manifest
                self.list.insert("end", f"{m.icon}  {m.name}  [{m.category}]  — {m.description[:40]}")

        def launch(self):
            sel = self.list.curselection()
            if not sel:
                return
            apps = self.registry.all()
            m = apps[sel[0]]
            win = tk.Toplevel(self)
            win.title(f"{m.icon} {m.name}")
            win.geometry("640x460")
            try:
                app = self.registry.launch(m.id)
                app.build(win)
            except Exception as e:
                tk.Label(win, text=f"启动失败: {e}").pack(pady=20)


def main():
    app = ToolboxApp()
    app.mainloop()


if __name__ == "__main__":
    main()
