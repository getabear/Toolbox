"""
App 注册表 —— 工具箱的"准入机制"。

规则:
  1. App 必须提供 manifest(元数据)才能被注册、被搜索、被启动。
  2. 注册后由 EnvManager 分配受管数据目录。
  3. registry.json 持久化安装状态;App 代码本身放在 apps/ 包里,
     通过 module 路径动态加载。
"""
from __future__ import annotations

import importlib
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from .env_manager import EnvManager

REQUIRED_FIELDS = ("id", "name", "version", "description", "module")


@dataclass
class Manifest:
    id: str
    name: str
    version: str
    description: str          # 自然语言描述,搜索会用到
    module: str               # 例如 "apps.demo_notepad"
    class_name: str = "ToolApp"
    category: str = "其他"
    icon: str = "🧰"          # emoji 或图片路径
    keywords: list[str] = field(default_factory=list)   # 同义词/别名,增强搜索
    entry_args: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Manifest":
        missing = [f for f in REQUIRED_FIELDS if f not in d]
        if missing:
            raise ValueError(f"manifest 缺少字段: {missing}")
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Registry:
    def __init__(self, env: EnvManager | None = None):
        self.env = env or EnvManager.instance()
        self.file = self.env.root / "registry.json"
        self._apps: dict[str, Manifest] = {}
        self._instances: dict[str, Any] = {}
        self.load()

    # ---- 持久化 ----
    def load(self) -> None:
        self._apps.clear()
        if self.file.exists():
            try:
                data = json.loads(self.file.read_text("utf-8"))
                for d in data.get("apps", []):
                    m = Manifest.from_dict(d)
                    self._apps[m.id] = m
            except (json.JSONDecodeError, OSError, ValueError):
                pass

    def save(self) -> None:
        payload = {"apps": [m.to_dict() for m in self._apps.values()]}
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
        self.save()
        return m

    def unregister(self, app_id: str, remove_data: bool = False) -> None:
        self._instances.pop(app_id, None)
        self._apps.pop(app_id, None)
        if remove_data:
            self.env.remove_app_data(app_id)
        self.save()

    # ---- 查询 ----
    def all(self) -> list[Manifest]:
        return list(self._apps.values())

    def get(self, app_id: str) -> Manifest | None:
        return self._apps.get(app_id)

    def categories(self) -> list[str]:
        seen: dict[str, None] = {}
        for m in self._apps.values():
            seen.setdefault(m.category, None)
        return list(seen)

    # ---- 启动 ----
    def launch(self, app_id: str):
        """动态加载 App 类并实例化,注入受管环境。"""
        m = self._apps.get(app_id)
        if m is None:
            raise KeyError(f"未注册的 App: {app_id}")
        if app_id in self._instances:
            return self._instances[app_id]
        module = importlib.import_module(m.module)
        klass = getattr(module, m.class_name)
        instance = klass(manifest=m, env=self.env.environment_for(m.id))
        self._instances[app_id] = instance
        return instance
