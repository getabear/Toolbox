# 🧰 Toolbox 工具箱

> Windows 平台的可扩展小工具集合 —— 受管环境 · 自然语言搜索 · 插件式扩展
>
> 深色现代界面(Python + CustomTkinter),MIT 开源。

![Python](https://img.shields.io/badge/Python-3.9%2B-blue) ![Platform](https://img.shields.io/badge/platform-Windows-green) ![License](https://img.shields.io/badge/license-MIT-orange)

## ✨ 特性

- **🖥 现代化界面** — CustomTkinter 深色主题,侧边栏导航 + 卡片式工具列表
- **🔍 智能搜索** — 支持关键字、拼写容错(`notpad` 也能搜到便签)、**自然语言描述**(试试搜「每天要打卡的任务」)
- **🗂 环境管理** — 每个工具的数据/配置/缓存/日志都被沙箱化管理,统一存放在 `%APPDATA%\Toolbox\`(可在环境管理页**更改数据目录**,自动搬迁、支持跨盘),内置磁盘占用查看、一键清缓存、彻底删数据
- **🔌 插件系统** — 外部用户**不用改源码**:把一个 `.py` 插件文件丢进插件目录,点「扫描安装」即接入(卡片/分类/搜索/数据沙箱全自动)。详见 [插件开发指南](docs/PLUGIN_GUIDE.md)
- **↕ 卡片排版** — 首页「排版」模式可调整工具卡片顺序,自动持久化

## 📦 内置工具

| 工具 | 分类 | 说明 |
|---|---|---|
| 🎵 音频播放器 | 音视频 | 播放 WAV / PCM 裸数据,可拖进度条,可设采样率(8k~96k)、位深(8/16/24/32)、通道数,带波形显示 |
| ✅ 每日任务 | 效率 | 快速添加/删除待办,点击完成弹出鼓励语,超过 3 天未完成自动置顶提醒,已完成任务归档可查 |
| 📝 便签 | 效率 | 简单记事本,Ctrl+S 保存,数据自动落入受管目录(也是新工具接入的示例模板) |

## 🚀 快速开始

### 方式一:下载 exe(最简单)

到 [Releases](https://github.com/getabear/Toolbox/releases) 页面下载 `Toolbox.exe`,双击运行,无需安装 Python。

### 方式二:源码运行

```bat
git clone https://github.com/getabear/Toolbox.git
cd Toolbox
pip install -r requirements.txt
python main.py
```

要求:Windows 10/11,Python 3.9+。

### 自己打包成 exe

```bat
build.bat
```

产物在 `dist\Toolbox.exe`(脚本会自动安装 pyinstaller)。

## 📖 使用说明

- **搜索**:顶部搜索框输入任意内容,实时过滤。支持关键字(`音频`、`todo`)、容错拼写(`notpad` → 便签)、自然语言(`想把声音文件放出来听` → 音频播放器)
- **分类**:左侧边栏按分类浏览
- **排版**:首页右上「↕ 排版」进入排版模式,卡片出现「← 左移 / 右移 →」按钮(排版模式下点击卡片=左移、右键=右移),顺序自动保存,重启不丢
- **插件管理**:侧边栏「🧩 插件管理」→「📄 生成插件模板」+「📂 打开插件目录」+「🔄 扫描安装」,三步装上你自己的工具;插件出错会单独提示,不影响主程序
- **环境管理**:侧边栏「🗂 环境管理」可查看每个工具的磁盘占用,清理缓存、删除数据(带二次确认),还可**更改数据根目录**(自动搬迁,支持跨盘,失败自动回滚)
- **数据存储位置**:所有工具数据统一在 `%APPDATA%\Toolbox\apps\<工具id>\`,卸载即删,不留垃圾

## 🔧 如何添加你自己的工具

### 外部用户:插件方式(推荐,不用改源码)

一个 `.py` 文件搞定,丢进插件目录即可:

```python
# my_tool.py —— 放到 %APPDATA%\Toolbox\plugins\ 下
import customtkinter as ctk

MANIFEST = {
    "id": "my_tool",
    "name": "我的工具",
    "version": "1.0.0",
    "description": "用自然语言写清楚它干嘛的 —— 搜索靠这段话",
    "category": "效率",
    "icon": "🔧",
    "keywords": ["别名", "同义词"],
    "class_name": "MyTool",
}

try:
    from core.base_app import ToolApp
except ImportError:
    class ToolApp:
        def __init__(self, manifest, env):
            self.manifest, self.env = manifest, env

class MyTool(ToolApp):
    def build(self, root):
        # root 是你的容器,随便搭界面
        # 数据用 self.data_path("x.db"),配置用 self.env.get_config()/save_config()
        ctk.CTkLabel(root, text="Hello Toolbox!").pack(pady=20)
```

然后在 Toolbox 的「插件管理」页点「🔄 扫描安装」。
完整文档(API、目录插件、生命周期、FAQ)见 **[docs/PLUGIN_GUIDE.md](docs/PLUGIN_GUIDE.md)**。
更省事:插件管理页点「📄 生成插件模板」,拿现成的掷骰子示例照着改。

### 内置开发者:随源码发布

在 `apps/` 下新建模块(继承 `ToolApp`),再往 `main.py` 的 `BUILTIN_APPS` 加一条 manifest
(需多写 `"module": "apps.my_tool"` 字段),工具自动出现在首页、分类和搜索里。

## 🏗 架构

```
Toolbox/
├── main.py              # 入口:主窗口、侧边栏、搜索、卡片排版、插件/环境管理页
├── core/
│   ├── env_manager.py   # 环境管理:每 App 独立沙箱 data/config/cache/logs,数据目录可迁移
│   ├── registry.py      # 注册表:manifest 准入、动态加载、插件目录扫描、卡片排序持久化
│   ├── search.py        # 搜索引擎:关键字+模糊(rapidfuzz)+自然语言(中文bigram)
│   └── base_app.py      # ToolApp 基类
├── apps/                # 内置工具
│   ├── audio_player.py
│   ├── daily_tasks.py
│   └── demo_notepad.py
├── docs/
│   └── PLUGIN_GUIDE.md  # 插件开发指南(外部用户从这里开始)
├── test_plugins.py      # 插件系统+排序回归测试
├── requirements.txt
└── build.bat            # PyInstaller 一键打包
```

第三方插件放在数据目录的 `plugins/` 下(单文件或目录形态),启动/扫描时自动加载,与源码解耦。

**搜索评分**:精确/前缀命中 > 关键字 > 分类 > 描述包含 > 模糊匹配(容错拼写)> 多词语义覆盖度(中文按 bigram 分词)。纯本地计算,无联网、无模型依赖。

## 🤝 贡献

欢迎提 Issue / PR!加新工具、改界面、优化搜索都可以。大改动建议先开 Issue 讨论。

## 📄 License

[MIT](LICENSE) © 2026 getabear
