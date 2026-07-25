from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from app.common.logging import configure_logging


def _preload_optional_runtimes() -> None:
    """在 Qt 修改 Windows DLL 搜索环境前加载可选的原生推理运行时。"""
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        # ONNX Runtime 是可选依赖；未安装时由具体后端给出操作提示。
        pass


def _configure_frozen_qt_plugins() -> None:
    """Prefer PyQt's platform plugins over OpenCV's bundled Qt plugins."""
    if not getattr(sys, "frozen", False):
        return
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    plugin_root = bundle_root / "PyQt5" / "Qt5" / "plugins"
    platform_plugins = plugin_root / "platforms"
    if platform_plugins.is_dir():
        os.environ["QT_PLUGIN_PATH"] = str(plugin_root)
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(platform_plugins)


def main() -> int:
    configure_logging()
    _preload_optional_runtimes()
    try:
        from PyQt5.QtWidgets import QApplication, QMessageBox
        from app.ui.main_window import MainWindow
    except Exception as exc:
        logging.getLogger(__name__).critical("GUI 初始化失败: %s", exc)
        return 2
    _configure_frozen_qt_plugins()
    app = QApplication(sys.argv)
    app.setApplicationName("RDK X5 Vision GUI")

    def handle_exception(exc_type, exc, traceback):
        logging.getLogger(__name__).exception("未捕获异常", exc_info=(exc_type, exc, traceback))
        QMessageBox.critical(None, "程序错误", str(exc))

    sys.excepthook = handle_exception
    window = MainWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
