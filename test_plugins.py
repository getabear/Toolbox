# -*- coding: utf-8 -*-
"""插件系统 + 排版功能测试(无GUI逻辑层)。"""
import sys, os, tempfile, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import EnvManager, Registry, Manifest
import main as tbmain

results = []
def check(name, cond, extra=""):
    results.append(bool(cond))
    s = ""
    if extra is not None and str(extra) != "":
        s = f"  {extra}"
    print(("[PASS] " if cond else "[FAIL] ") + name + s)

root = tempfile.mkdtemp(prefix="tb_plugin_")
EnvManager._instance = None
env = EnvManager(root=root)
reg = Registry(env)

# 内置注册
for d in tbmain.BUILTIN_APPS:
    reg.register(Manifest.from_dict(d))
check("内置注册", len(reg.all()) == 3)

# --- 单文件插件 ---
pdir = reg.plugins_dir
(pdir / "hello_plugin.py").write_text(tbmain.PLUGIN_TEMPLATE, "utf-8")
rep = reg.sync_plugins()
check("单文件插件安装", rep["added"] == ["hello_dice"], rep)
m = reg.get("hello_dice")
check("插件manifest字段", m.source == "plugin" and m.name == "掷骰子" and m.icon == "🎲")
check("插件参与排序列表", reg.ordered_ids()[-1] == "hello_dice")

# 搜索能找到插件
from core import SearchEngine
se = SearchEngine(reg.all())
r = se.search("想掷个骰子玩玩")
check("插件可被自然语言搜索", r and r[0].manifest.id == "hello_dice", r[0].reason if r else "")

# --- 目录插件 ---
d = pdir / "multi_tool"
d.mkdir()
(d / "plugin.json").write_text(json.dumps({
    "id": "multi_tool", "name": "多文件工具", "version": "0.2.0",
    "description": "目录形态插件测试", "category": "测试", "icon": "📦",
    "class_name": "MultiTool", "entry": "main_view.py"}, ensure_ascii=False), "utf-8")
(d / "utils.py").write_text("HELLO = 'from-utils'\n", "utf-8")
(d / "main_view.py").write_text(
    "import utils\nMANIFEST_HINT = utils.HELLO\nclass MultiTool:\n    pass\n", "utf-8")
rep = reg.sync_plugins()
check("目录插件安装", "multi_tool" in rep["added"], rep)
mm = reg.get("multi_tool")
check("目录插件entry加载", mm.source == "plugin" and mm.path.endswith("main_view.py"))

# --- 坏插件不影响其他 ---
(pdir / "bad_plugin.py").write_text("MANIFEST = {'id': 'bad'}  # 缺字段\n", "utf-8")
rep = reg.sync_plugins()
check("坏插件报错但系统正常", len(rep["errors"]) == 1 and "bad_plugin" in rep["errors"][0], rep["errors"])
check("好插件仍在", reg.get("hello_dice") is not None and reg.get("multi_tool") is not None)
(pdir / "bad_plugin.py").unlink()

# --- id 冲突 ---
(pdir / "conflict.py").write_text(
    "MANIFEST = {'id':'demo_notepad','name':'x','version':'1','description':'x','module':'x'}\n", "utf-8")
rep = reg.sync_plugins()
check("id冲突被拒", any("冲突" in e for e in rep["errors"]), rep["errors"])
(pdir / "conflict.py").unlink()

# --- 删除插件文件后自动注销 ---
(pdir / "hello_plugin.py").unlink()
rep = reg.sync_plugins()
check("文件删除自动注销", rep["removed"] == ["hello_dice"], rep)
check("注销后查询为空", reg.get("hello_dice") is None)
check("内置不受影响", len([m for m in reg.all() if m.source == "builtin"]) == 3)
# 数据保留验证
check("插件数据目录保留", (env.root / "apps" / "hello_dice").exists())

# --- 排序 ---
ids0 = [m.id for m in reg.all()]
ok = reg.move_app(ids0[0], 1)
ids1 = [m.id for m in reg.all()]
check("move_app 后移", ok and ids1[0] == ids0[1] and ids1[1] == ids0[0], f"{ids0} -> {ids1}")
ok = reg.move_app(ids1[0], -1)  # 首位再左移应越界失败
check("首位左移越界返回False", not ok)
ok = reg.move_app(ids1[1], -1)  # 第2位左移,还原原始顺序
ids2 = [m.id for m in reg.all()]
check("move_app 前移还原", ok and ids2 == ids0, f"{ids1} -> {ids2}")

# 持久化:重载 Registry 顺序保持
reg2 = Registry(env)
check("排序持久化", [m.id for m in reg2.all()] == ids0)

# set_order
reg2.set_order(["daily_tasks", "audio_player", "demo_notepad", "multi_tool"])
check("set_order 生效", [m.id for m in reg2.all()][:2] == ["daily_tasks", "audio_plugin".replace("plugin","player")])

print(f"\n==== {sum(results)}/{len(results)} PASSED ====")
sys.exit(0 if all(results) else 1)
