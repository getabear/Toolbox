"""
App 注册表 —— 工具箱的"准入机制"。

规则:
  1. App 必须提供 manifest(元数据)才能被注册、被搜索、被启动。
  2. 注册后由 EnvManager 分配受管数据目录。
  3. registry.json 持久化安装状态与卡片排序;内置 App 代码放在 apps/ 包,
     外部插件放在 <数据根目录>/plugins/ 下,启动时自动扫描注册。

外部插件两种形态:
  A. 单文件: plugins/my_tool.py,文件内定义 MANIFEST = {...} 和工具类
  B. 目录:   plugins/my_tool/plugin.json + 若干 .py 文件
插件文件删除后,下次同步自动注销注册(数据保留,可在环境管理页删除)。
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from .env_manager import EnvManager

REQUIRED_FIELDS = ("id", "name", "version", "description", "module")
PLUGIN_DIRNAME = "plugins"


@dataclass
class Manifest:
    id: str
    name: str
    version: str
    description: str          # 自然语言描述,搜索会用到
    module: str               # 内置: "apps.demo_notepad";插件: 自动生成的模块名
    class_name: str = "ToolApp"
    category: str = "其他"
    icon: str = "🧰"          # emoji 或图片路径
    keywords: list[str] = field(default_factory=list)   # 同义词/别名,增强搜索
    entry_args: dict[str, Any] = field(default_factory=dict)
    source: str = "builtin"   # builtin=内置 / plugin=外部插件
    path: str = ""            # 插件入口文件绝对路径(source=plugin 时有效)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Manifest":
        missing = [f for f in REQUIRED_FIELDS if f not in d]
        if missing:
            raise ValueError(f"manifest 缺少字段: {missing}")
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PluginError(Exception):
    pass


class Registry:
    def __init__(self, env: EnvManager | None = None):
        self.env = env or EnvManager.instance()
        self.file = self.env.root / "registry.json"
        self._apps: dict[str, Manifest] = {}
        self._instances: dict[str, Any] = {}
        self._order: list[str] = []            # 卡片排序(用户可调整)
        self._plugin_modules: dict[str, Any] = {}  # 已加载的插件模块缓存
        self.load()

    # ---- 持久化 ----
    def load(self) -> None:
        self._apps.clear()
        self._order = []
        if self.file.exists():
            try:
                data = json.loads(self.file.read_text("utf-8"))
                for d in data.get("apps", []):
                    m = Manifest.from_dict(d)
                    self._apps[m.id] = m
                self._order = [i for i in data.get("order", []) if i in self._apps]
            except (json.JSONDecodeError, OSError, ValueError):
                pass

    def save(self) -> None:
        payload = {"apps": [m.to_dict() for m in self._apps.values()],
                   "order": self.ordered_ids()}
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")
        tmp.replace(self.file)

    # ---- 注册 / 卸载 ----
    def register(self, manifest: Manifest | dict[str, Any]) -> Manifest:
        m = manifest if isinstance(manifest, Manifest) else Manifest.from_dict(manifest)
        if m.id in self._apps:
            raise ValueError(f"App 已注册: {m.id}")
        # 注册即分配受管环境(创建目录结构)
        self.env.environment_for(m.id)
        self._apps[m.id] = m
        self._order.append(m.id)
        self.save()
        return m

    def update_manifest(self, manifest: Manifest) -> None:
        """就地更新已注册 App 的 manifest(插件升级用),保持排序位置。"""
        if manifest.id not in self._apps:
            raise KeyError(manifest.id)
        self._apps[manifest.id] = manifest
        self._instances.pop(manifest.id, None)
        self.save()

    def unregister(self, app_id: str, remove_data: bool = False) -> None:
        self._instances.pop(app_id, None)
        self._plugin_modules.pop(app_id, None)
        self._apps.pop(app_id, None)
        if app_id in self._order:
            self._order.remove(app_id)
        if remove_data:
            self.env.remove_app_data(app_id)
        self.save()

    # ---- 查询 ----
    def ordered_ids(self) -> list[str]:
        ids = [i for i in self._order if i in self._apps]
        ids += [k for k in self._apps if k not in set(ids)]
        return ids

    def all(self) -> list[Manifest]:
        """按用户自定义顺序返回全部 manifest。"""
        return [self._apps[i] for i in self.ordered_ids()]

    def get(self, app_id: str) -> Manifest | None:
        return self._apps.get(app_id)

    def categories(self) -> list[str]:
        seen: dict[str, None] = {}
        for m in self.all():
            seen.setdefault(m.category, None)
        return list(seen)

    # ---- 排序 ----
    def move_app(self, app_id: str, delta: int) -> bool:
        """把 app 在展示顺序中前移/后移 delta 位。越界返回 False。"""
        ids = self.ordered_ids()
        if app_id not in ids:
            return False
        i = ids.index(app_id)
        j = i + delta
        if j < 0 or j >= len(ids):
            return False
        ids[i], ids[j] = ids[j], ids[i]
        self._order = ids
        self.save()
        return True

    def set_order(self, ordered_ids: list[str]) -> None:
        ids = [i for i in ordered_ids if i in self._apps]
        ids += [k for k in self._apps if k not in set(ids)]
        self._order = ids
        self.save()

    # ---- 插件目录 ----
    @property
    def plugins_dir(self) -> Path:
        d = self.env.root / PLUGIN_DIRNAME
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def _load_module_from_file(path: Path, mod_name: str):
        spec = importlib.util.spec_from_file_location(mod_name, str(path))
        if spec is None or spec.loader is None:
            raise PluginError(f"无法加载插件文件: {path}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)
        return mod

    def _scan_plugin_file(self, py: Path) -> Manifest | None:
        """单文件插件:模块顶层定义 MANIFEST dict。"""
        if py.name.startswith("_") or py.name.startswith("."):
            return None
        mod_name = f"toolbox_plugin_{py.stem}"
        mod = self._load_module_from_file(py, mod_name)
        data = getattr(mod, "MANIFEST", None)
        if not isinstance(data, dict):
            raise PluginError(f"{py.name}: 缺少 MANIFEST 字典")
        data = dict(data)
        data.setdefault("module", mod_name)
        m = Manifest.from_dict(data)
        m.source = "plugin"
        m.path = str(py.resolve())
        self._plugin_modules[m.id] = mod
        return m

    def _scan_plugin_dir(self, d: Path) -> Manifest | None:
        """目录插件:必须含 plugin.json,entry 指定入口 .py。"""
        pj = d / "plugin.json"
        if not pj.exists():
            return None
        data = json.loads(pj.read_text("utf-8"))
        entry = data.pop("entry", None) or f"{d.name}.py"
        entry_path = d / entry
        if not entry_path.exists():
            raise PluginError(f"{d.name}: 入口文件不存在 {entry}")
        mod_name = f"toolbox_plugin_{d.name}"
        if str(d) not in sys.path:
            sys.path.insert(0, str(d))
        mod = self._load_module_from_file(entry_path, mod_name)
        data.setdefault("module", mod_name)
        m = Manifest.from_dict(data)
        m.source = "plugin"
        m.path = str(entry_path.resolve())
        self._plugin_modules[m.id] = mod
        return m

    def sync_plugins(self) -> dict[str, list[str]]:
        """扫描插件目录:新插件注册、旧插件更新、文件已删的插件注销。

        返回 {"added": [...], "updated": [...], "removed": [...], "errors": [...]}
        单个插件出错不影响其他插件。
        """
        result: dict[str, list[str]] = {"added": [], "updated": [], "removed": [], "errors": []}
        pdir = self.plugins_dir
        found: dict[str, Manifest] = {}

        for py in sorted(pdir.glob("*.py")):
            try:
                m = self._scan_plugin_file(py)
                if m:
                    found[m.id] = m
            except Exception as e:
                result["errors"].append(f"{py.name}: {e}")
        for sub in sorted(p for p in pdir.iterdir() if p.is_dir()):
            try:
                m = self._scan_plugin_dir(sub)
                if m:
                    found[m.id] = m
            except Exception as e:
                result["errors"].append(f"{sub.name}/: {e}")

        # 注销:已注册为插件但文件已消失
        for pid in [i for i, m in self._apps.items() if m.source == "plugin"]:
            if pid not in found:
                self.unregister(pid)
                result["removed"].append(pid)

        # 注册或更新
        for pid, m in found.items():
            if pid in self._apps:
                old = self._apps[pid]
                if old.source == "builtin":
                    result["errors"].append(f"{pid}: 与内置工具 id 冲突,插件被忽略")
                    continue
                if old.to_dict() != m.to_dict():
                    self.update_manifest(m)
                    result["updated"].append(pid)
            else:
                self.register(m)
                result["added"].append(pid)
        return result

    # ---- 启动 ----
    def launch(self, app_id: str):
        """动态加载 App 类并实例化,注入受管环境。"""
        m = self._apps.get(app_id)
        if m is None:
            raise KeyError(f"未注册的 App: {app_id}")
        if app_id in self._instances:
            return self._instances[app_id]
        if m.source == "plugin":
            module = self._plugin_modules.get(app_id)
            if module is None:
                module = self._load_module_from_file(Path(m.path), m.module)
                self._plugin_modules[app_id] = module
        else:
            module = importlib.import_module(m.module)
        klass = getattr(module, m.class_name)
        instance = klass(manifest=m, env=self.env.environment_for(m.id))
        self._instances[app_id] = instance
        return instance
