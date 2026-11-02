# 🧰 Toolbox 工具箱

> Windows 平台的可扩展小工具集合 —— 受管环境 · 自然语言搜索 · 插件式扩展
>
> 深色现代界面(Python + CustomTkinter),MIT 开源。

![Python](https://img.shields.io/badge/Python-3.9%2B-blue) ![Platform](https://img.shields.io/badge/platform-Windows-green) ![License](https://img.shields.io/badge/license-MIT-orange)

## ✨ 特性

- **🖥 现代化界面** — CustomTkinter 深色主题,侧边栏导航 + 卡片式工具列表
- **🔍 智能搜索** — 支持关键字、拼写容错(`notpad` 也能搜到便签)、**自然语言描述**(试试搜「每天要打卡的任务」)
- **🗂 环境管理** — 每个工具的数据/配置/缓存/日志都被沙箱化管理,统一存放在 `%APPDATA%\Toolbox\`,内置磁盘占用查看、一键清缓存、彻底删数据
- **🔌 插件式扩展** — 加一个新工具只需写一个类 + 注册一条 manifest,界面/搜索/环境管理自动生效,零改动

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
- **环境管理**:侧边栏「🗂 环境管理」可查看每个工具的磁盘占用,清理缓存或删除全部数据(带二次确认)
- **数据存储位置**:所有工具数据统一在 `%APPDATA%\Toolbox\apps\<工具id>\`,卸载即删,不留垃圾

## 🔧 如何添加你自己的工具

**两步接入,界面零改动:**

1️⃣ 在 `apps/` 下新建 `my_tool.py`:

```python
from core.base_app import ToolApp

class MyTool(ToolApp):
    def build(self, root):
        # root 是你的容器,随便搭界面
        # 数据用 self.data_path("x.db"),配置用 self.config()/self.save_config()
        ...

    def on_close(self):
        ...  # 可选:退出时保存状态
```

2️⃣ 在 `main.py` 的 `BUILTIN_APPS` 里加一条:

```python
{
    "id": "my_tool",
    "name": "我的工具",
    "version": "0.1.0",
    "description": "用自然语言写清楚它干嘛的 —— 搜索靠这段话",
    "module": "apps.my_tool",
    "class_name": "MyTool",
    "category": "效率",
    "icon": "🔧",
    "keywords": ["别名", "同义词"],
},
```

完成!工具自动出现在首页、分类和搜索结果里,数据目录自动受管。

## 🏗 架构

```
Toolbox/
├── main.py              # 入口:主窗口、侧边栏、搜索、卡片、环境管理页
├── core/
│   ├── env_manager.py   # 环境管理:每 App 独立沙箱 data/config/cache/logs
│   ├── registry.py      # 注册表:manifest 准入、动态加载
│   ├── search.py        # 搜索引擎:关键字+模糊(rapidfuzz)+自然语言(中文bigram)
│   └── base_app.py      # ToolApp 基类
├── apps/                # 工具都放这里
│   ├── audio_player.py
│   ├── daily_tasks.py
│   └── demo_notepad.py
├── requirements.txt
└── build.bat            # PyInstaller 一键打包
```

**搜索评分**:精确/前缀命中 > 关键字 > 分类 > 描述包含 > 模糊匹配(容错拼写)> 多词语义覆盖度(中文按 bigram 分词)。纯本地计算,无联网、无模型依赖。

## 🤝 贡献

欢迎提 Issue / PR!加新工具、改界面、优化搜索都可以。大改动建议先开 Issue 讨论。

## 📄 License

[MIT](LICENSE) © 2026 getabear
