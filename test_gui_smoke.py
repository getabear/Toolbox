# -*- coding: utf-8 -*-
"""PySide6 GUI 冒烟测试:临时数据根,遍历所有页面/交互,不触碰真实用户数据。

用法:  python test_gui_smoke.py     (需要图形环境或设置 QT_QPA_PLATFORM=offscreen)
"""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QPlainTextEdit, QPushButton

from core import EnvManager

root = tempfile.mkdtemp(prefix="tb_gui_")
EnvManager._instance = None
EnvManager(root=root)

import main as tbmain

results = []


def check(name, cond, extra=""):
    results.append(bool(cond))
    s = f"  {extra}" if extra is not None and str(extra) != "" else ""
    print(("[PASS] " if cond else "[FAIL] ") + name + s)


app = QApplication(sys.argv)
app.setStyle("Fusion")
tbmain.apply_dark_palette(app)
win = tbmain.ToolboxWindow()
win.show()
app.processEvents()


def page_cards():
    """只查当前页(避免命中等待销毁的旧页控件)。"""
    return win.stack.currentWidget().findChildren(tbmain.ToolCard)


def page_buttons(text=None, contains=None):
    btns = win.stack.currentWidget().findChildren(QPushButton)
    if text:
        btns = [b for b in btns if b.text() == text]
    if contains:
        btns = [b for b in btns if contains in b.text()]
    return btns


# 1. 首页
check("首页渲染3张卡片", len(page_cards()) == 3, len(page_cards()))

# 2. 搜索防抖
win.search_box.setText("音频")
app.processEvents()
check("搜索输入后未立即渲染(防抖)", len(page_cards()) == 3)
time.sleep(0.25)
app.processEvents()
res = page_cards()
check("搜索'音频'命中1张卡", len(res) == 1 and res[0].app_id == "audio_player")
win.search_box.setText("想把声音文件放出来听")
time.sleep(0.25)
app.processEvents()
res = page_cards()
check("自然语言搜索命中音频播放器", res and res[0].app_id == "audio_player",
      [c.app_id for c in res])
win.search_box.clear()
time.sleep(0.25)
app.processEvents()
check("清空搜索回全部工具", len(page_cards()) == 3)

# 3. 排版模式
win._toggle_arrange()
app.processEvents()
cards = page_cards()
check("排版模式卡片带移动按钮", cards and cards[0]._arrange)
ids0 = [m.id for m in win.registry.all()]
win._move_app(ids0[0], 1)
app.processEvents()
ids1 = [m.id for m in win.registry.all()]
check("排版右移生效并持久化", ids1[0] == ids0[1] and ids1[1] == ids0[0], f"{ids0}->{ids1}")
win._move_app(ids1[0], -1)
app.processEvents()
win._toggle_arrange()
app.processEvents()
check("退出排版模式", not win._arrange_mode)

# 4. 启动三个工具
for aid in ("demo_notepad", "daily_tasks", "audio_player"):
    win._launch(aid)
    app.processEvents()
    check(f"启动 {aid}", win._app_pages.get(aid) is not None)
    win._show_home()
    app.processEvents()

# 5. 便签:写入并保存
win._launch("demo_notepad")
app.processEvents()
notepad = win.registry._instances["demo_notepad"]
pe = win.stack.currentWidget().findChild(QPlainTextEdit)
pe.setPlainText("冒烟测试内容")
page_buttons(text="保存")[0].click()
app.processEvents()
check("便签保存落盘", notepad.data_path("notes.txt").read_text("utf-8") == "冒烟测试内容")
win._show_home()
app.processEvents()

# 6. 每日任务:添加/完成/还原/删除
win._launch("daily_tasks")
app.processEvents()
tasks = win.registry._instances["daily_tasks"]
le = win.stack.currentWidget().findChild(QLineEdit)
le.setText("冒烟任务A")
page_buttons(contains="添加")[0].click()
app.processEvents()
check("任务添加", len(tasks.tasks) == 1 and tasks.tasks[0]["title"] == "冒烟任务A")
page_buttons(contains="✔ 完成")[0].click()
app.processEvents()
check("任务完成+toast", tasks.tasks[0]["done"] and tasks._toast_widget is not None)
page_buttons(contains="已完成")[0].click()
app.processEvents()
check("已完成页有还原按钮", len(page_buttons(contains="还原")) == 1)
page_buttons(contains="还原")[0].click()
app.processEvents()
check("还原生效", not tasks.tasks[0]["done"])
page_buttons(text="🗑")[0].click()
app.processEvents()
check("删除生效", len(tasks.tasks) == 0)
win._show_home()
app.processEvents()

# 7. 音频播放器:解码逻辑 + UI 装载 + seek
try:
    import wave
    import struct
    import numpy as np
    from apps.audio_player import pcm_to_float32, read_wav, PlaybackEngine, fmt_time

    wav_path = os.path.join(root, "test.wav")
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(struct.pack("<" + "h" * 16000,
                                  *[int(20000 * np.sin(i / 20)) for i in range(16000)]))
    data, sr, ch, bd = read_wav(wav_path)
    check("WAV 解析", data.shape == (16000, 1) and sr == 16000 and bd == 16)
    check("PCM 8bit 解码", pcm_to_float32(bytes([128, 255, 0]), 8, 1).shape == (3, 1))
    check("PCM 24bit 解码",
          abs(pcm_to_float32(b"\x00\x00\x00" + b"\xff\xff\xff", 24, 1)[0][0]) < 1e-6)
    check("fmt_time", fmt_time(125) == "02:05")
    eng = PlaybackEngine()
    eng.load(data, 16000, 1)
    eng.seek_fraction(0.5)
    check("引擎 seek", abs(eng.fraction - 0.5) < 0.01)

    win._launch("audio_player")
    app.processEvents()
    ap = win.registry._instances["audio_player"]
    ap._load_file(wav_path)
    app.processEvents()
    check("播放器 UI 装载 WAV", ap.engine.data is not None and ap.wave._peaks is not None)
    ap._wave_seek(0.25)
    app.processEvents()
    check("波形点击 seek", abs(ap.engine.fraction - 0.25) < 0.02)
    # 播完后:finished 置位、真实点击播放按钮从头开始(回归:旧版 finished 依赖 is_playing 导致卡死)
    ap.engine._pos = len(ap.engine.data)
    check("播完后 finished 置位", ap.engine.finished)
    _orig_play = ap.engine.play
    ap.engine.play = lambda: True   # 无声卡环境下打桩,只验证按钮→回卷链路
    ap._set_play_text(False)
    ap.play_btn.click()             # 走真实信号路径,不直接调 _toggle_play
    app.processEvents()
    check("播完后点播放按钮从头开始", ap.engine._pos == 0 and ap.engine.finished is False)
    ap.engine.play = _orig_play
    ap._stop()
    win._show_home()
    app.processEvents()
except ImportError as e:
    print(f"[SKIP] 音频测试(缺依赖: {e})")

# 8. 插件管理页 + 生成模板 + 扫描安装 + 启动 + 卸载
win._show_plugins_page()
app.processEvents()
labels = [l.text() for l in win.stack.currentWidget().findChildren(QLabel)]
check("插件页渲染", any("插件管理" in t for t in labels))
win._make_plugin_template()
app.processEvents()
check("模板生成", (win.registry.plugins_dir / "hello_plugin.py").exists())
win._rescan_plugins()
app.processEvents()
check("模板插件扫描安装", win.registry.get("hello_dice") is not None)
win._launch("hello_dice")
app.processEvents()
check("启动插件工具", win._app_pages.get("hello_dice") is not None)
roll_btn = [b for b in win.stack.currentWidget().findChildren(QPushButton) if b.text() == "掷!"]
roll_btn[0].click()
app.processEvents()
check("插件掷骰按钮",
      win.registry._instances["hello_dice"].env.get_config().get("rolls") == 1)
win._show_home()
app.processEvents()

import PySide6.QtWidgets as QW
_orig_q = QW.QMessageBox.question
QW.QMessageBox.question = staticmethod(lambda *a, **k: QW.QMessageBox.Yes)
win._uninstall_plugin(win.registry.get("hello_dice"))
QW.QMessageBox.question = _orig_q
app.processEvents()
check("卸载插件", win.registry.get("hello_dice") is None)

# 9. 环境管理页
win._show_env_page()
app.processEvents()
labels = [l.text() for l in win.stack.currentWidget().findChildren(QLabel)]
check("环境页渲染", any("数据根目录" in t for t in labels)
      and any(str(root) in t for t in labels))
win._clear_cache("demo_notepad")
app.processEvents()
check("清缓存不崩", True)

# 10. 分类导航
win._show_home(category="效率")
app.processEvents()
check("分类筛选", len(page_cards()) == 2)

# 10b. 侧边栏分类按钮真实点击(回归:clicked(checked) 曾覆盖 lambda 默认参数)
nav_btns = win.sidebar.findChildren(QPushButton)
eff_btn = [b for b in nav_btns if "效率" in b.text()][0]
av_btn = [b for b in nav_btns if "音视频" in b.text()][0]
eff_btn.click()
app.processEvents()
texts = [l.text() for l in win.stack.currentWidget().findChildren(QLabel)]
check("侧边栏点'效率'筛选", len(page_cards()) == 2
      and any("全部工具 · 效率" in t for t in texts), len(page_cards()))
av_btn.click()
app.processEvents()
texts = [l.text() for l in win.stack.currentWidget().findChildren(QLabel)]
check("侧边栏点'音视频'筛选", len(page_cards()) == 1
      and any("全部工具 · 音视频" in t for t in texts), len(page_cards()))

# 关闭
win.close()
app.processEvents()
check("关闭时 on_close 调用", len(win._launched_apps) >= 3)

print(f"\n==== {sum(results)}/{len(results)} PASSED ====")
sys.exit(0 if all(results) else 1)
