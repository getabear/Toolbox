"""App 基类 —— 每个接入工具箱的工具都继承它。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

try:
    from PySide6.QtWidgets import QWidget
except ImportError:  # 无 GUI 环境(纯逻辑测试)下允许导入本模块
    QWidget = object  # type: ignore[assignment,misc]

if TYPE_CHECKING:
    from .env_manager import AppEnvironment
    from .registry import Manifest


class ToolApp(ABC):
    """
    约定:
      - build(root): 在给定父容器(QWidget)中构建界面(由主程序调用)。
        给 root 设置布局(QVBoxLayout(root) 等)后自由添加控件。
      - on_close(): 主窗口关闭时调用,App 在此保存状态。
      - self.env: 受管环境,数据一律写到 env.data_dir / env.cache_dir,
        配置用 env.get_config/save_config,禁止散落写注册表或用户目录。
    """

    def __init__(self, manifest: "Manifest", env: "AppEnvironment"):
        self.manifest = manifest
        self.env = env
        self.log = env.get_logger()

    @abstractmethod
    def build(self, root: "QWidget") -> None:
        """构建工具界面。root 是父容器 QWidget。"""

    def on_close(self) -> None:
        """可选:退出时保存状态。"""

    # 便捷方法
    def data_path(self, name: str):
        return self.env.data_dir / name

    def config(self) -> dict:
        return self.env.get_config()

    def save_config(self, cfg: dict) -> None:
        self.env.save_config(cfg)
