"""
Toolbox 主程序 —— 现代化图形界面 (PySide6 / Qt)。

布局:
┌──────────┬─────────────────────────────────┐
│ 侧边栏    │  🔍 搜索栏(关键字 + 自然语言)   │
│ · 首页    │  ┌────┐ ┌────┐ ┌────┐          │
│ · 分类    │  │工具卡│ │工具卡│ │工具卡│  …      │
│ · 环境    │  └────┘ └────┘ └────┘          │
│          │  (点击卡片 → 右侧/全屏运行工具)   │
└──────────┴─────────────────────────────────┘

运行:  pip install -r requirements.txt && python main.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

try:
    from PySide6.QtCore import Qt, QUrl, QTimer, Signal
    from PySide6.QtGui import QDesktopServices, QFont, QIcon
    from PySide6.QtWidgets import (
        QApplication, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
        QLineEdit, QMainWindow, QMessageBox, QPushButton, QScrollArea,
        QStackedWidget, QVBoxLayout, QWidget,
    )
except ImportError:
    sys.stderr.write("缺少 PySide6,请先执行: pip install PySide6-Essentials\n")
    raise

from core import EnvManager, Registry, SearchEngine, Manifest, human_size
from core.env_manager import default_root as main_env_default_root

ACCENT = "#4f8cff"
SIDEBAR_BG = "#1a1d24"
MAIN_BG = "#12141a"
CARD_BG = "#1e222c"
CARD_HOVER = "#252b38"
CARD_BORDER = "#2a2f3a"
TEXT_MAIN = "#e6e9ef"
TEXT_DIM = "#8a93a6"
TEXT_MID = "#9aa3b5"
GREEN = "#5cbf7a"
ORANGE = "#e8a54b"

# 全局样式:hover/圆角全部交给 Qt 样式表(原生渲染,不再像 Tk 那样软件重绘)
GLOBAL_QSS = f"""
QMainWindow {{ background: {MAIN_BG}; }}
QWidget#mainArea {{ background: {MAIN_BG}; }}
QFrame#sidebar {{ background: {SIDEBAR_BG}; }}
QLabel {{ color: {TEXT_MAIN}; background: transparent; }}
QLineEdit#searchBox {{
    background: {CARD_BG}; border: 1px solid {CARD_BORDER}; border-radius: 10px;
    padding: 8px 14px; color: {TEXT_MAIN}; font-size: 14px;
    selection-background-color: {ACCENT};
}}
QLineEdit#searchBox:focus {{ border-color: {ACCENT}; }}
QPushButton {{
    background: {ACCENT}; color: white; border: none; border-radius: 8px;
    padding: 7px 16px; font-size: 13px;
}}
QPushButton:hover {{ background: #6ba0ff; }}
QPushButton:pressed {{ background: #3d7ae8; }}
QPushButton[kind="nav"] {{
    background: transparent; color: {TEXT_MAIN}; text-align: left;
    border-radius: 8px; padding: 8px 14px; font-size: 14px;
}}
QPushButton[kind="nav"]:hover {{ background: #2a2f3a; }}
QPushButton[kind="dim"] {{ background: #2a2f3a; color: {TEXT_MAIN}; }}
QPushButton[kind="dim"]:hover {{ background: #3a4150; }}
QPushButton[kind="danger"] {{ background: #5a2730; color: {TEXT_MAIN}; }}
QPushButton[kind="danger"]:hover {{ background: #7a3540; }}
QPushButton[kind="ok"] {{ background: #27402e; color: {TEXT_MAIN}; }}
QPushButton[kind="ok"]:hover {{ background: #35563e; }}
QFrame#panel {{ background: {CARD_BG}; border: none; border-radius: 12px; }}
QLabel#toast {{
    background: #2a2f3a; color: {TEXT_MAIN}; border-radius: 8px;
    padding: 8px 14px; font-size: 13px;
}}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
QScrollBar::handle:vertical {{ background: #2a2f3a; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #3a4150; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: #2a2f3a; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QComboBox {{
    background: {CARD_BG}; color: {TEXT_MAIN}; border: 1px solid {CARD_BORDER};
    border-radius: 7px; padding: 5px 10px; min-height: 20px;
}}
QComboBox:hover {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {CARD_BG}; color: {TEXT_MAIN};
    selection-background-color: {ACCENT}; selection-color: white;
    border: 1px solid {CARD_BORDER}; outline: none;
}}
QComboBox QAbstractItemView::item {{
    min-height: 26px; padding: 2px 10px;
    background: {CARD_BG}; color: {TEXT_MAIN};
}}
QComboBox QAbstractItemView::item:hover {{ background: {CARD_HOVER}; }}
QComboBox QAbstractItemView::item:selected {{ background: {ACCENT}; color: white; }}
QPlainTextEdit, QTextEdit {{
    background: {CARD_BG}; color: {TEXT_MAIN}; border: 1px solid {CARD_BORDER};
    border-radius: 10px; padding: 8px; selection-background-color: {ACCENT};
}}
QSlider::groove:horizontal {{ height: 6px; background: #2a2f3a; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 3px; }}
QSlider::handle:horizontal {{
    width: 14px; height: 14px; margin: -4px 0;
    background: {ACCENT}; border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{ background: #6ba0ff; }}
QMessageBox {{ background: {MAIN_BG}; }}
"""

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
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout

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
        """root 是你的界面容器(QWidget),自己给它设置布局,随意发挥。"""
        lay = QVBoxLayout(root)
        lay.setContentsMargins(16, 16, 16, 16)

        self.result = QLabel("🎲")
        f = self.result.font(); f.setPointSize(48); self.result.setFont(f)
        self.result.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.result)
        lay.addSpacing(20)

        # ③ 数据存取:一律走 self.env(受管沙箱),别写死路径
        cfg = self.env.get_config({"rolls": 0})
        self.count = QLabel(f"历史掷骰 {cfg.get('rolls', 0)} 次")
        self.count.setStyleSheet("color: #8a93a6;")
        self.count.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.count)

        def roll():
            n = random.randint(1, 6)
            self.result.setText(["⚀","⚁","⚂","⚃","⚄","⚅"][n-1])
            cfg["rolls"] = cfg.get("rolls", 0) + 1
            self.env.save_config(cfg)
            self.count.setText(f"历史掷骰 {cfg['rolls']} 次")

        btn = QPushButton("掷!")
        btn.setFixedSize(120, 38)
        btn.clicked.connect(roll)
        lay.addWidget(btn, 0, Qt.AlignHCenter)
        lay.addStretch(1)

    def on_close(self):
        """可选:窗口关闭时清理/保存。"""
        pass
'''


class ToolCard(QFrame):
    """首页工具卡片。hover 高亮由样式表处理;子 Label 鼠标穿透,点击统一落在卡片上。"""

    clicked = Signal(str)          # 普通模式:启动;排版模式:左移
    right_clicked = Signal(str)    # 排版模式:右移

    def __init__(self, m: Manifest, reason: str = "",
                 arrange_mode: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.app_id = m.id
        self._arrange = arrange_mode
        self.setObjectName("toolCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(150)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 10)
        lay.setSpacing(2)

        icon = QLabel(m.icon)
        f = icon.font(); f.setPointSize(22); icon.setFont(f)
        lay.addWidget(icon)

        name = QLabel(m.name)
        f = name.font(); f.setPointSize(12); f.setBold(True); name.setFont(f)
        lay.addWidget(name)

        cat = QLabel(m.category + ("  · 插件" if m.source == "plugin" else ""))
        cat.setStyleSheet(f"color: {ACCENT}; font-size: 11px;")
        lay.addWidget(cat)

        desc_text = m.description if len(m.description) <= 46 else m.description[:45] + "…"
        desc = QLabel(desc_text)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {TEXT_MID}; font-size: 12px;")
        lay.addWidget(desc)

        if arrange_mode:
            mv = QWidget()
            mv.setStyleSheet("background: transparent;")
            hl = QHBoxLayout(mv)
            hl.setContentsMargins(0, 6, 0, 0)
            hl.setSpacing(6)
            left = QPushButton("← 左移")
            right = QPushButton("右移 →")
            for b in (left, right):
                b.setProperty("kind", "dim")
                b.setFixedSize(70, 26)
                b.setCursor(Qt.ArrowCursor)
            left.clicked.connect(lambda: self.clicked.emit(self.app_id))
            right.clicked.connect(lambda: self.right_clicked.emit(self.app_id))
            hl.addWidget(left)
            hl.addWidget(right)
            hl.addStretch(1)
            lay.addWidget(mv)
        elif reason:
            r = QLabel(f"✓ {reason}")
            r.setStyleSheet(f"color: {GREEN}; font-size: 10px;")
            lay.addWidget(r)
        else:
            v = QLabel(f"v{m.version}")
            v.setStyleSheet("color: #5c6474; font-size: 10px;")
            lay.addWidget(v)
        lay.addStretch(1)

        # 子 Label 鼠标穿透 → hover/点击统一落在卡片上(替代 tk 版递归绑定)
        for w in self.findChildren(QLabel):
            w.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        border = ACCENT if arrange_mode else CARD_BORDER
        self.setStyleSheet(f"""
            QFrame#toolCard {{
                background: {CARD_BG}; border: 1px solid {border}; border-radius: 14px;
            }}
            QFrame#toolCard:hover {{ background: {CARD_HOVER}; border-color: {ACCENT}; }}
            QFrame#toolCard QLabel {{ background: transparent; border: none; }}
        """)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.clicked.emit(self.app_id)
        elif ev.button() == Qt.RightButton and self._arrange:
            self.right_clicked.emit(self.app_id)


class ToolboxWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Toolbox 工具箱")
        self.resize(1080, 680)
        self.setMinimumSize(860, 540)

        self.env = EnvManager.instance()
        self.registry = Registry(self.env)
        self._plugin_report = seed_registry(self.registry)
        self.search_engine = SearchEngine(self.registry.all())
        self._arrange_mode = False
        self._app_pages: dict[str, QWidget] = {}    # 已构建的工具页(缓存复用)
        self._launched_apps: list = []              # 关闭时逐个 on_close
        self._search_timer = QTimer(self)           # 搜索防抖:停止输入 180ms 才渲染
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(180)
        self._search_timer.timeout.connect(self._do_search)

        self.setStyleSheet(GLOBAL_QSS)
        self._build_layout()
        self._show_home()

    # ---------- 布局 ----------
    def _build_layout(self):
        central = QWidget()
        central.setObjectName("mainArea")
        self.setCentralWidget(central)
        root_lay = QHBoxLayout(central)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # 侧边栏
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(190)
        sb = QVBoxLayout(self.sidebar)
        sb.setContentsMargins(16, 24, 16, 16)
        sb.setSpacing(2)

        title = QLabel("🧰 Toolbox")
        f = title.font(); f.setPointSize(16); f.setBold(True); title.setFont(f)
        sb.addWidget(title)
        sub = QLabel("受管 · 可搜索 · 可扩展")
        sub.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px;")
        sb.addWidget(sub)
        sb.addSpacing(12)

        self.sidebar_items = QWidget()
        self.sidebar_items.setStyleSheet("background: transparent;")
        self.sidebar_items_lay = QVBoxLayout(self.sidebar_items)
        self.sidebar_items_lay.setContentsMargins(0, 0, 0, 0)
        self.sidebar_items_lay.setSpacing(2)
        sb.addWidget(self.sidebar_items, 1)
        self._rebuild_sidebar()
        root_lay.addWidget(self.sidebar)

        # 主区域
        main = QWidget()
        main.setObjectName("mainArea")
        ml = QVBoxLayout(main)
        ml.setContentsMargins(20, 16, 20, 16)
        ml.setSpacing(8)

        self.search_box = QLineEdit()
        self.search_box.setObjectName("searchBox")
        self.search_box.setFixedHeight(40)
        self.search_box.setPlaceholderText(
            "🔍  搜索工具:输入关键字,或用自然语言描述,如「能把图片压小一点的」")
        self.search_box.textChanged.connect(self._on_search_text)
        ml.addWidget(self.search_box)

        self.stack = QStackedWidget()
        ml.addWidget(self.stack, 1)
        root_lay.addWidget(main, 1)

    def _rebuild_sidebar(self):
        """重建侧边栏导航(分类变化后调用,如安装/卸载插件)。"""
        lay = self.sidebar_items_lay
        while lay.count():
            item = lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self._nav_button("🏠  首页", self._show_home)
        cats = self.registry.categories()
        if cats:
            lab = QLabel("分类")
            f = lab.font(); f.setBold(True); lab.setFont(f)
            lab.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
            lay.addSpacing(16)
            lay.addWidget(lab)
            for c in cats:
                self._nav_button(f"▸  {c}", lambda _=False, cc=c: self._show_home(category=cc))

        lab = QLabel("系统")
        f = lab.font(); f.setBold(True); lab.setFont(f)
        lab.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        lay.addSpacing(16)
        lay.addWidget(lab)
        self._nav_button("🧩  插件管理", self._show_plugins_page)
        self._nav_button("🗂  环境管理", self._show_env_page)
        lay.addStretch(1)

    def _nav_button(self, text: str, command) -> QPushButton:
        btn = QPushButton(text)
        btn.setProperty("kind", "nav")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(command)
        self.sidebar_items_lay.addWidget(btn)
        return btn

    # ---------- 页面切换 ----------
    def _set_page(self, widget: QWidget):
        cur = self.stack.currentWidget()
        if cur is widget:
            return
        if cur is not None:
            self.stack.removeWidget(cur)
            # 工具页有缓存要复用;首页/管理页是临时构建的,直接销毁
            if not any(cur is w for w in self._app_pages.values()):
                cur.deleteLater()
        self.stack.addWidget(widget)
        self.stack.setCurrentWidget(widget)

    # ---------- 首页 / 搜索 ----------
    def _show_home(self, category: str | None = None):
        self.search_box.blockSignals(True)
        self.search_box.clear()
        self.search_box.blockSignals(False)
        self._search_timer.stop()
        apps = self.registry.all()
        if category:
            apps = [m for m in apps if m.category == category]
        title = f"全部工具 · {category}" if category else "全部工具"
        self._set_page(self._build_cards_page(title, apps))

    def _on_search_text(self, _text: str):
        self._search_timer.start()   # 防抖:连续输入时不重复渲染

    def _do_search(self):
        q = self.search_box.text().strip()
        if not q:
            self._set_page(self._build_cards_page("全部工具", self.registry.all()))
            return
        results = self.search_engine.search(q)
        if results:
            self._set_page(self._build_cards_page(
                f"「{q}」的搜索结果 · {len(results)} 项",
                [r.manifest for r in results],
                reasons={r.manifest.id: r.reason for r in results}))
        else:
            page = QWidget()
            lay = QVBoxLayout(page)
            lab = QLabel(f"😕 没有找到与「{q}」相关的工具\n试试换个说法?")
            lab.setStyleSheet(f"color: {TEXT_DIM}; font-size: 16px;")
            lab.setAlignment(Qt.AlignCenter)
            lay.addWidget(lab)
            self._set_page(page)

    def _build_cards_page(self, title: str, apps: list[Manifest],
                          reasons: dict | None = None) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        t = QLabel(title)
        f = t.font(); f.setPointSize(14); f.setBold(True); t.setFont(f)
        hl.addWidget(t)
        hl.addStretch(1)
        if self._arrange_mode:
            hint = QLabel("用 ← → 调整工具位置,顺序自动保存")
            hint.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
            hl.addWidget(hint)
            btn = QPushButton("✔ 完成排版")
            btn.setProperty("kind", "ok")
        else:
            btn = QPushButton("↕ 排版")
            btn.setProperty("kind", "dim")
        btn.setFixedWidth(110)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(self._toggle_arrange)
        hl.addWidget(btn)
        lay.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 8, 0)
        grid.setSpacing(8)
        for i in range(4):
            grid.setColumnStretch(i, 1)

        arrangeable = not reasons
        for idx, m in enumerate(apps):
            r, c = divmod(idx, 4)
            card = ToolCard(m, (reasons or {}).get(m.id, ""),
                            arrange_mode=self._arrange_mode and arrangeable)
            if self._arrange_mode and arrangeable:
                card.clicked.connect(lambda aid: self._move_app(aid, -1))
                card.right_clicked.connect(lambda aid: self._move_app(aid, 1))
            else:
                card.clicked.connect(self._launch)
            grid.addWidget(card, r, c)
        grid.setRowStretch(len(apps) // 4 + 1, 1)

        if not apps:
            empty = QLabel("暂无工具。点侧边栏「🧩 插件管理」安装第三方工具,\n"
                           "或在 main.py 的 BUILTIN_APPS 中注册内置工具。")
            empty.setStyleSheet(f"color: {TEXT_DIM};")
            empty.setAlignment(Qt.AlignCenter)
            grid.addWidget(empty, 0, 0, 1, 4)

        scroll.setWidget(container)
        lay.addWidget(scroll, 1)
        return page

    def _toggle_arrange(self):
        self._arrange_mode = not self._arrange_mode
        self._refresh_current_view()

    def _move_app(self, app_id: str, delta: int):
        if self.registry.move_app(app_id, delta):
            self.search_engine.update(self.registry.all())
            self._refresh_current_view()

    def _refresh_current_view(self):
        """按当前搜索框内容重渲染(排版切换/移动卡片后调用)。"""
        if self.search_box.text().strip():
            self._do_search()
        else:
            self._set_page(self._build_cards_page("全部工具", self.registry.all()))

    # ---------- 工具启动 ----------
    def _launch(self, app_id: str):
        page = self._app_pages.get(app_id)
        if page is None:
            try:
                app = self.registry.launch(app_id)
            except Exception as e:
                self._toast(f"启动失败: {e}")
                return
            page = self._make_tool_page(app)
            self._app_pages[app_id] = page
            self._launched_apps.append(app)
        self._set_page(page)

    def _make_tool_page(self, app) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        bar = QWidget()
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(0, 0, 0, 0)
        m = app.manifest
        t = QLabel(f"{m.icon} {m.name}")
        f = t.font(); f.setPointSize(13); f.setBold(True); t.setFont(f)
        bl.addWidget(t)
        bl.addStretch(1)
        back = QPushButton("← 返回")
        back.setProperty("kind", "dim")
        back.setFixedWidth(90)
        back.setCursor(Qt.PointingHandCursor)
        back.clicked.connect(self._show_home)
        bl.addWidget(back)
        lay.addWidget(bar)

        body = QWidget()
        lay.addWidget(body, 1)
        app.build(body)
        return page

    # ---------- 插件管理页 ----------
    def _show_plugins_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        t = QLabel("🧩 插件管理")
        f = t.font(); f.setPointSize(14); f.setBold(True); t.setFont(f)
        lay.addWidget(t)

        intro = QFrame()
        intro.setObjectName("panel")
        il = QVBoxLayout(intro)
        il.setContentsMargins(16, 12, 16, 12)
        txt = QLabel("安装第三方工具:把插件 .py 文件放进插件目录,点「扫描安装」即可。\n"
                     f"插件目录:{self.registry.plugins_dir}\n"
                     "开发文档:仓库 docs/PLUGIN_GUIDE.md")
        txt.setStyleSheet(f"color: {TEXT_MID}; font-size: 12px;")
        il.addWidget(txt)
        lay.addWidget(intro)

        btns = QWidget()
        bl = QHBoxLayout(btns)
        bl.setContentsMargins(0, 0, 0, 0)
        for text, slot, kind in (
                ("📂 打开插件目录", self._open_plugins_dir, None),
                ("🔄 扫描安装", self._rescan_plugins, None),
                ("📄 生成插件模板", self._make_plugin_template, "dim")):
            b = QPushButton(text)
            if kind:
                b.setProperty("kind", kind)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(slot)
            bl.addWidget(b)
        bl.addStretch(1)
        lay.addWidget(btns)

        # 上次扫描报告
        rep = self._plugin_report
        msgs = []
        if rep.get("added"):   msgs.append("新装: " + ", ".join(rep["added"]))
        if rep.get("updated"): msgs.append("更新: " + ", ".join(rep["updated"]))
        if rep.get("removed"): msgs.append("已移除: " + ", ".join(rep["removed"]))
        if rep.get("errors"):  msgs.append("⚠ " + " | ".join(rep["errors"]))
        if msgs:
            rep_lab = QLabel("  ".join(msgs))
            rep_lab.setStyleSheet(f"color: {ORANGE}; font-size: 12px;")
            rep_lab.setWordWrap(True)
            lay.addWidget(rep_lab)

        # 已安装插件列表
        plugins = [m for m in self.registry.all() if m.source == "plugin"]
        table = QFrame()
        table.setObjectName("panel")
        tl = QVBoxLayout(table)
        tl.setContentsMargins(14, 10, 14, 10)
        if not plugins:
            empty = QLabel("尚未安装任何插件")
            empty.setStyleSheet("color: #5c6474;")
            empty.setAlignment(Qt.AlignCenter)
            tl.addWidget(empty)
            tl.addStretch(1)
        else:
            for m in plugins:
                row = QWidget()
                row.setStyleSheet("background: transparent;")
                rl = QHBoxLayout(row)
                rl.setContentsMargins(0, 4, 0, 4)
                n = QLabel(f"{m.icon} {m.name}")
                f = n.font(); f.setBold(True); n.setFont(f)
                n.setFixedWidth(150)
                v = QLabel(f"v{m.version} · {m.category}")
                v.setStyleSheet(f"color: {TEXT_DIM};")
                v.setFixedWidth(120)
                p = QLabel(str(m.path))
                p.setStyleSheet("color: #5c6474; font-size: 10px;")
                un = QPushButton("卸载")
                un.setProperty("kind", "danger")
                un.setFixedSize(60, 26)
                un.setCursor(Qt.PointingHandCursor)
                un.clicked.connect(lambda _=False, mm=m: self._uninstall_plugin(mm))
                rl.addWidget(n)
                rl.addWidget(v)
                rl.addWidget(p, 1)
                rl.addWidget(un)
                tl.addWidget(row)
            tl.addStretch(1)
        lay.addWidget(table, 1)
        self._set_page(page)

    def _open_plugins_dir(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.registry.plugins_dir)))

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
        ret = QMessageBox.question(
            self, "卸载插件",
            f"卸载「{m.name}」?\n将从注册表移除。插件文件和数据目录保留,\n"
            f"如要彻底删除,请手动删文件和在环境管理页删数据。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ret != QMessageBox.Yes:
            return
        self.registry.unregister(m.id)
        self.search_engine.update(self.registry.all())
        self._app_pages.pop(m.id, None)
        self._rebuild_sidebar()
        self._show_plugins_page()
        self._toast(f"已卸载 {m.name}")

    # ---------- 环境管理页 ----------
    def _show_env_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        t = QLabel("🗂 环境管理")
        f = t.font(); f.setPointSize(14); f.setBold(True); t.setFont(f)
        lay.addWidget(t)

        info = QFrame()
        info.setObjectName("panel")
        ig = QGridLayout(info)
        ig.setContentsMargins(16, 12, 16, 12)
        ig.setColumnStretch(1, 1)
        rows = [
            ("数据根目录", str(self.env.root)),
            ("注册表", str(self.registry.file)),
            ("已注册 App", f"{len(self.registry.all())} 个"),
            ("磁盘占用", human_size(self.env.total_usage_bytes())),
        ]
        for i, (k, v) in enumerate(rows):
            kl = QLabel(k)
            kl.setStyleSheet(f"color: {TEXT_DIM};")
            vl = QLabel(v)
            vl.setStyleSheet("font-size: 12px;")
            vl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            ig.addWidget(kl, i, 0, Qt.AlignLeft)
            ig.addWidget(vl, i, 1, Qt.AlignLeft)

        chg = QWidget()
        chg.setStyleSheet("background: transparent;")
        cl = QHBoxLayout(chg)
        cl.setContentsMargins(0, 4, 0, 0)
        b1 = QPushButton("📁 更改数据目录…")
        b1.setFixedWidth(150)
        b1.setCursor(Qt.PointingHandCursor)
        b1.clicked.connect(self._change_data_root)
        b2 = QPushButton("恢复默认位置")
        b2.setProperty("kind", "dim")
        b2.setFixedWidth(110)
        b2.setCursor(Qt.PointingHandCursor)
        b2.clicked.connect(lambda: self._apply_new_root(main_env_default_root()))
        hint = QLabel("更改后旧数据自动搬迁(可跨盘)")
        hint.setStyleSheet("color: #5c6474; font-size: 11px;")
        cl.addWidget(b1)
        cl.addWidget(b2)
        cl.addWidget(hint)
        cl.addStretch(1)
        ig.addWidget(chg, len(rows), 0, 1, 2)
        lay.addWidget(info)

        # 各 App 数据表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        table = QFrame()
        table.setObjectName("panel")
        tg = QGridLayout(table)
        tg.setContentsMargins(14, 12, 14, 12)
        tg.setColumnStretch(1, 1)
        heads = ("App", "数据目录", "占用", "操作")
        for c, h in enumerate(heads):
            hl = QLabel(h)
            f = hl.font(); f.setBold(True); hl.setFont(f)
            hl.setStyleSheet(f"color: {TEXT_DIM};")
            tg.addWidget(hl, 0, c)
        for r, m in enumerate(self.registry.all(), start=1):
            appenv = self.env.environment_for(m.id)
            tg.addWidget(QLabel(f"{m.icon} {m.name}"), r, 0)
            pl = QLabel(str(appenv.base))
            pl.setStyleSheet(f"color: {TEXT_MID}; font-size: 11px;")
            tg.addWidget(pl, r, 1)
            tg.addWidget(QLabel(human_size(appenv.usage_bytes())), r, 2)
            btns = QWidget()
            btns.setStyleSheet("background: transparent;")
            bl = QHBoxLayout(btns)
            bl.setContentsMargins(0, 0, 0, 0)
            bl.setSpacing(6)
            cb = QPushButton("清缓存")
            cb.setProperty("kind", "dim")
            cb.setFixedSize(70, 26)
            cb.setCursor(Qt.PointingHandCursor)
            cb.clicked.connect(lambda _=False, a=m.id: self._clear_cache(a))
            db = QPushButton("删数据")
            db.setProperty("kind", "danger")
            db.setFixedSize(70, 26)
            db.setCursor(Qt.PointingHandCursor)
            db.clicked.connect(lambda _=False, a=m.id: self._remove_data(a))
            bl.addWidget(cb)
            bl.addWidget(db)
            tg.addWidget(btns, r, 3)
        scroll.setWidget(table)
        lay.addWidget(scroll, 1)
        self._set_page(page)

    def _clear_cache(self, app_id: str):
        freed = self.env.environment_for(app_id).clear_cache()
        self._toast(f"{app_id} 缓存已清理,释放 {human_size(freed)}")
        self._show_env_page()

    def _change_data_root(self):
        path = QFileDialog.getExistingDirectory(
            self, "选择新的数据目录", str(self.env.root.parent))
        if not path:
            return
        ret = QMessageBox.question(
            self, "确认更改",
            f"数据目录将更改为:\n{path}\n\n旧数据会自动搬迁过去,继续吗?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ret == QMessageBox.Yes:
            self._apply_new_root(path)

    def _apply_new_root(self, new_root):
        try:
            self.env.change_root(new_root)
        except OSError as e:
            self._toast(f"❌ {e}")
            return
        # 重建注册表与搜索引擎(指向新 root)
        self.registry = Registry(self.env)
        self._plugin_report = seed_registry(self.registry)
        self.search_engine.update(self.registry.all())
        self._app_pages.clear()
        self._launched_apps.clear()
        self._rebuild_sidebar()
        self._toast(f"✅ 数据目录已更改为 {Path(new_root)}")
        self._show_env_page()

    def _remove_data(self, app_id: str):
        ret = QMessageBox.question(
            self, "确认",
            f"彻底删除 {app_id} 的所有数据?\n(注册信息保留,数据不可恢复)",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ret == QMessageBox.Yes:
            self.env.remove_app_data(app_id)
            self._show_env_page()

    # ---------- Toast ----------
    def _toast(self, msg: str):
        t = QLabel(msg, self)
        t.setObjectName("toast")
        t.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        t.adjustSize()
        t.move((self.width() - t.width()) // 2, self.height() - t.height() - 50)
        t.show()
        t.raise_()
        QTimer.singleShot(2600, t.deleteLater)

    # ---------- 关闭 ----------
    def closeEvent(self, ev):
        for app in self._launched_apps:
            try:
                app.on_close()
            except Exception:
                pass
        super().closeEvent(ev)


def apply_dark_palette(app) -> None:
    """给 QApplication 设深色调色板。

    QSS 管不到 QComboBox 的下拉弹出层(原生弹出窗口不吃父级样式表),
    Fusion 风格下弹出层颜色取自调色板 —— 不设就会白底灰字看不清。
    """
    from PySide6.QtGui import QColor, QPalette
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(MAIN_BG))
    pal.setColor(QPalette.WindowText, QColor(TEXT_MAIN))
    pal.setColor(QPalette.Base, QColor(CARD_BG))
    pal.setColor(QPalette.AlternateBase, QColor(CARD_HOVER))
    pal.setColor(QPalette.Text, QColor(TEXT_MAIN))
    pal.setColor(QPalette.Button, QColor(CARD_BG))
    pal.setColor(QPalette.ButtonText, QColor(TEXT_MAIN))
    pal.setColor(QPalette.Highlight, QColor(ACCENT))
    pal.setColor(QPalette.HighlightedText, QColor("white"))
    pal.setColor(QPalette.ToolTipBase, QColor(CARD_BG))
    pal.setColor(QPalette.ToolTipText, QColor(TEXT_MAIN))
    pal.setColor(QPalette.PlaceholderText, QColor(TEXT_DIM))
    app.setPalette(pal)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    apply_dark_palette(app)
    # 窗口/任务栏图标:PyInstaller onefile 资源解包在 sys._MEIPASS,源码运行在项目根
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    ico = base / "toolbox.ico"
    if ico.exists():
        app.setWindowIcon(QIcon(str(ico)))
    font = QFont("Microsoft YaHei UI", 10)
    app.setFont(font)
    win = ToolboxWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
