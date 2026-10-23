"""Yuzhong Chunsheng desktop translator entry point."""

from __future__ import annotations

import ctypes
import os
import sys
import traceback

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import QApplication, QMessageBox

from lingua.config import APP_ID, config_dir, log_path
from lingua.branding import make_brand_icon
from lingua.main_window import MainWindow
from lingua.theme import APP_QSS


def _make_icon() -> QIcon:
    return make_brand_icon(256)


def _install_exception_handler(app: QApplication) -> None:
    def handle_exception(exc_type, exc_value, exc_tb) -> None:  # type: ignore[no-untyped-def]
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        details = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            config_dir().mkdir(parents=True, exist_ok=True)
            with log_path().open("a", encoding="utf-8") as handle:
                handle.write(details + "\n")
        except OSError:
            pass
        QMessageBox.critical(
            None,
            "羽中纯声遇到错误",
            f"程序遇到未处理的错误：\n{exc_value}\n\n详细信息已写入：\n{log_path()}",
        )

    sys.excepthook = handle_exception


def run() -> int:
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName("羽中纯声")
    app.setApplicationDisplayName("羽中纯声")
    app.setOrganizationName(APP_ID)
    app.setQuitOnLastWindowClosed(False)
    app.setFont(QFont("Microsoft YaHei UI", 9))
    app.setStyleSheet(APP_QSS)

    if os.name == "nt":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "YuzhongChunsheng.Translator.Desktop.1"
            )
        except Exception:
            pass

    icon = _make_icon()
    app.setWindowIcon(icon)
    _install_exception_handler(app)

    window = MainWindow()
    window.setWindowIcon(icon)
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(run())

