"""
环境管理器 —— 工具箱的"沙箱管家"。

所有接入工具箱的 App 必须通过 EnvManager 申请运行环境:
  <ROOT>/
    registry.json            # 已注册 App 清单
    apps/<app_id>/
        data/                # 应用数据(文档、数据库等)
        config.json          # 应用配置
        cache/               # 缓存(可随时清理)
        logs/                # 日志

ROOT 位置:
  Windows : %APPDATA%\\Toolbox
  macOS   : ~/Library/Application Support/Toolbox
  Linux   : ~/.local/share/Toolbox
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any

APP_NAME = "Toolbox"


def default_root() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / APP_NAME


class AppEnvironment:
    """单个 App 的受管环境句柄。App 代码只能拿到这个,拿不到全局路径。"""

    def __init__(self, manager: "EnvManager", app_id: str):
        self._m = manager
        self.app_id = app_id
        self.base: Path = manager.root / "apps" / app_id

    # ---- 目录 ----
    @property
    def data_dir(self) -> Path:
        return self._ensure(self.base / "data")

    @property
    def cache_dir(self) -> Path:
        return self._ensure(self.base / "cache")

    @property
    def logs_dir(self) -> Path:
        return self._ensure(self.base / "logs")

    @staticmethod
    def _ensure(p: Path) -> Path:
        p.mkdir(parents=True, exist_ok=True)
        return p

    # ---- 配置 ----
    @property
    def config_file(self) -> Path:
        return self.base / "config.json"

    def get_config(self, default: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.config_file.exists():
            try:
                return json.loads(self.config_file.read_text("utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return default if default is not None else {}

    def save_config(self, cfg: dict[str, Any]) -> None:
        self.base.mkdir(parents=True, exist_ok=True)
        tmp = self.config_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), "utf-8")
        tmp.replace(self.config_file)

    def update_config(self, **kwargs: Any) -> None:
        cfg = self.get_config()
        cfg.update(kwargs)
        self.save_config(cfg)

    # ---- 日志 ----
    def get_logger(self, name: str | None = None) -> logging.Logger:
        logger = logging.getLogger(f"toolbox.{self.app_id}.{name or 'app'}")
        if not logger.handlers:
            handler = logging.FileHandler(self.logs_dir / "app.log", encoding="utf-8")
            handler.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    # ---- 统计与清理 ----
    def usage_bytes(self) -> int:
        total = 0
        for f in self.base.rglob("*"):
            if f.is_file():
                try:
                    total += f.stat().st_size
                except OSError:
                    pass
        return total

    def clear_cache(self) -> int:
        """清空缓存目录,返回释放字节数。"""
        freed = self.usage_bytes()
        cache = self.base / "cache"
        if cache.exists():
            shutil.rmtree(cache, ignore_errors=True)
        cache.mkdir(parents=True, exist_ok=True)
        before = self.usage_bytes()
        return freed - before


class EnvManager:
    """全局环境管理器(单例入口)。"""

    _instance: "EnvManager | None" = None

    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root else default_root()
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "apps").mkdir(exist_ok=True)
        EnvManager._instance = self

    @classmethod
    def instance(cls) -> "EnvManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def environment_for(self, app_id: str) -> AppEnvironment:
        """为 App 发放受管环境。app_id 需满足 [a-z0-9_-]。"""
        if not app_id or not all(c.isalnum() or c in "-_" for c in app_id.lower()):
            raise ValueError(f"非法 app_id: {app_id!r}")
        return AppEnvironment(self, app_id.lower())

    def total_usage_bytes(self) -> int:
        total = 0
        for f in self.root.rglob("*"):
            if f.is_file():
                try:
                    total += f.stat().st_size
                except OSError:
                    pass
        return total

    def remove_app_data(self, app_id: str) -> None:
        """卸载 App 时彻底删除其数据(调用方需二次确认)。"""
        shutil.rmtree(self.root / "apps" / app_id.lower(), ignore_errors=True)


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024  # type: ignore[assignment]
    return f"{n:.1f} GB"
