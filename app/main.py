from __future__ import annotations

import logging
import sys

from app.common.logging import configure_logging


def main() -> int:
    configure_logging()
    try:
        from PyQt5.QtWidgets import QApplication, QMessageBox
        from app.ui.main_window import MainWindow
    except Exception as exc:
        logging.getLogger(__name__).critical("GUI 初始化失败: %s", exc)
        return 2
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
