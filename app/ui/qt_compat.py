try:
    from PyQt5 import QtCore, QtGui, QtWidgets
except ImportError as exc:
    raise RuntimeError("未安装 PyQt5，请执行: uv sync --extra desktop") from exc

Signal = QtCore.pyqtSignal
Slot = QtCore.pyqtSlot

__all__ = ["QtCore", "QtGui", "QtWidgets", "Signal", "Slot"]
