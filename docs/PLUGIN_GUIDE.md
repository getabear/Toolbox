# Toolbox 插件开发指南

不用改一行 Toolbox 源码,一个 `.py` 文件就能把你的工具装进工具箱:
自动出现在首页卡片、分类侧边栏、搜索结果里,数据自动受环境管理。

## 30 秒上手

1. 打开 Toolbox → 侧边栏「🧩 插件管理」→ 点「📄 生成插件模板」
2. 点「📂 打开插件目录」,把生成的 `hello_plugin.py` 复制一份改改
3. 回 Toolbox 点「🔄 扫描安装」—— 你的工具已经出现在首页了

插件目录位置:`%APPDATA%\Toolbox\plugins\`
(如果更改过数据目录,则在 `<新数据目录>\plugins\`)

## 插件的两种形态

### 形态 A:单文件插件(推荐)

一个 `.py` 文件放进插件目录,包含两部分:

```python
# -*- coding: utf-8 -*-
"""我的工具:一句话说明。"""
import customtkinter as ctk

# ① MANIFEST:元数据(必填)
MANIFEST = {
    "id": "my_tool",                 # 全局唯一,小写字母/数字/下划线/连字符
    "name": "我的工具",               # 显示名称
    "version": "1.0.0",
    "description": "用自然语言写清楚它是干嘛的 —— 搜索靠这段话!",
    "category": "效率",               # 侧边栏分类
    "icon": "🔧",                     # emoji 即可
    "keywords": ["别名", "同义词", "english"],  # 增强搜索命中
    "class_name": "MyTool",           # 下面工具类的类名
}

# ② 工具类:必须继承 ToolApp
try:
    from core.base_app import ToolApp
except ImportError:   # 开发调试兜底
    class ToolApp:
        def __init__(self, manifest, env):
            self.manifest, self.env = manifest, env

class MyTool(ToolApp):
    def build(self, root):
        """构建界面。root 是给你的容器 frame,用 pack/grid 随意布局。"""
        ctk.CTkLabel(root, text="Hello Toolbox!").pack(pady=20)

    def on_close(self):
        """可选:主窗口关闭时调用,用来保存状态。"""
```

要点:
- `MANIFEST` 必须是模块顶层的字典,`class_name` 指向的类必须存在
- 文件名不要以 `_` 或 `.` 开头(会被跳过)
- 依赖第三方库(如 numpy)需要用户自己 pip install,插件里请 `try import` 并给出友好提示

### 形态 B:目录插件(多文件工具)

```
plugins/my_tool/
├── plugin.json      # 元数据(字段同 MANIFEST,外加 "entry")
├── main_view.py     # 入口文件(entry 指向它)
└── utils.py         # 其他模块,入口内正常 import
```

`plugin.json`:

```json
{
    "id": "my_tool",
    "name": "我的工具",
    "version": "1.0.0",
    "description": "……",
    "category": "效率",
    "icon": "🔧",
    "keywords": [],
    "class_name": "MyTool",
    "entry": "main_view.py"
}
```

插件目录会被自动加入 `sys.path`,入口文件里可以直接 `import utils`。

## 数据存取规范(重要)

工具的所有数据必须走注入的受管环境 `self.env`,**不要写死路径**:

```python
class MyTool(ToolApp):
    def build(self, root):
        # 数据文件:<数据根>/apps/my_tool/data/xxx
        db_file = self.data_path("my.db")          # = self.env.data_dir / "my.db"

        # 配置读写(JSON,自动落盘 apps/my_tool/config.json)
        cfg = self.env.get_config({"theme": "dark"})
        cfg["theme"] = "light"
        self.env.save_config(cfg)
        # 或一步到位: self.env.update_config(theme="light")

        # 缓存(用户可一键清理,别放重要数据):self.env.cache_dir
        # 日志(自动写 apps/my_tool/logs/app.log):
        self.log.info("工具启动了")
```

这样做的收益:用户在「环境管理」页能看到你的占用、一键清缓存;
用户更改数据目录(如搬到 D 盘)时你的数据自动跟着走。

## 生命周期

| 时机 | 发生什么 |
|---|---|
| 扫描安装 | Toolbox 加载模块、读取 MANIFEST、注册、分配数据沙箱 |
| 点击卡片 | 实例化你的类(`__init__(manifest=..., env=...)`),调用 `build(root)` |
| 再次点击 | 复用同一实例,`build` 只调一次 |
| 关闭 Toolbox | 调用你的 `on_close()` |
| 删除插件文件后扫描 | 自动注销(数据保留,可在环境管理页删除) |
| 修改 MANIFEST 后扫描 | 自动更新注册信息(版本号变了记得改) |

## 常见问题

**Q: 插件加载失败怎么办?**
插件管理页会显示错误原因(缺 MANIFEST、语法错误、类不存在等),单个插件出错不影响其他插件和主程序。

**Q: id 和内置工具冲突?**
插件会被忽略并提示冲突。换个 id。

**Q: 界面能用原生 tkinter 吗?**
能。`root` 就是普通 tk 容器,tk/customtkinter 控件都可以用。建议优先 customtkinter(已内置),风格统一。

**Q: 想要无界面的后台工具?**
当前版本面向 GUI 工具。`build(root)` 里可以放一个极简状态页,逻辑跑在后台线程。

**Q: 怎么调试?**
直接命令行 `python plugins/my_tool.py` 会报 ImportError(没有 ToolApp 上下文),
用文件里的 try/except 兜底类,或先写好逻辑函数单独测试,界面部分装进 Toolbox 测。

## 内置工具源码参考

仓库 `apps/` 目录下三个内置工具就是三种复杂度的样板:
- `demo_notepad.py` — 最简(文本框+保存)
- `daily_tasks.py` — 中等(JSON 持久化+列表渲染+toast)
- `audio_player.py` — 复杂(线程音频回调+Canvas 波形+可选依赖降级)
