"""Setup help for browser playback-time synchronization."""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import QUrl, Qt, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .widgets import Card


class PlayerSyncDialog(QDialog):
    manual_sync_requested = pyqtSignal()

    def __init__(
        self,
        extension_dir: Path,
        port: int,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.extension_dir = extension_dir
        self.port = port
        self.setWindowTitle("播放器时间同步")
        self.setModal(False)
        self.resize(620, 520)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)
        title = QLabel("播放器时间同步")
        title.setObjectName("PageTitle")
        root.addWidget(title)
        subtitle = QLabel(
            "连接后，字幕和总结使用视频真实时间，点击时间引用可直接跳转。"
        )
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        card = Card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 17, 20, 17)
        card_layout.setSpacing(9)
        card_layout.addWidget(self._heading("Chrome / Edge 扩展"))
        steps = QLabel(
            "1. 打开 chrome://extensions 或 edge://extensions\n"
            "2. 开启右上角“开发者模式”\n"
            "3. 点击“加载已解压的扩展程序”\n"
            "4. 选择下面的 browser_extension 文件夹\n"
            "5. 刷新正在播放视频的网页"
        )
        steps.setWordWrap(True)
        steps.setStyleSheet("line-height:1.7;color:#4C3E41;")
        card_layout.addWidget(steps)
        self.path_label = QLabel(str(self.extension_dir))
        self.path_label.setObjectName("Faint")
        self.path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.path_label.setWordWrap(True)
        card_layout.addWidget(self.path_label)
        open_folder = QPushButton("打开扩展文件夹")
        open_folder.setObjectName("SecondaryButton")
        open_folder.clicked.connect(self._open_folder)
        card_layout.addWidget(open_folder, 0, Qt.AlignLeft)
        root.addWidget(card)

        manual_card = Card()
        manual_layout = QVBoxLayout(manual_card)
        manual_layout.setContentsMargins(20, 16, 20, 16)
        manual_layout.setSpacing(7)
        manual_layout.addWidget(self._heading("其他桌面播放器"))
        note = QLabel(
            "没有浏览器扩展时，可以手动输入当前播放到的时间。"
            "记录会使用真实视频时间，但无法自动控制播放器跳转。"
        )
        note.setObjectName("Hint")
        note.setWordWrap(True)
        manual_layout.addWidget(note)
        manual_button = QPushButton("手动同步当前时间")
        manual_button.setObjectName("SecondaryButton")
        manual_button.clicked.connect(self.manual_sync_requested.emit)
        manual_layout.addWidget(manual_button, 0, Qt.AlignLeft)
        root.addWidget(manual_card)
        root.addStretch()

        footer = QHBoxLayout()
        self.status = QLabel(f"本地桥接：127.0.0.1:{self.port}")
        self.status.setObjectName("Faint")
        footer.addWidget(self.status)
        footer.addStretch()
        close_button = QPushButton("关闭")
        close_button.setObjectName("PrimaryButton")
        close_button.setMinimumWidth(100)
        close_button.clicked.connect(self.close)
        footer.addWidget(close_button)
        root.addLayout(footer)

    @staticmethod
    def _heading(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("CardTitle")
        return label

    def set_connection(
        self,
        connected: bool,
        title: str = "",
        manual: bool = False,
    ) -> None:
        if connected and manual:
            self.status.setText("当前使用：手动时间同步")
            self.status.setStyleSheet(f"color:{theme.GREEN};")
        elif connected:
            detail = title.strip() or "网页视频"
            self.status.setText(f"已连接：{detail[:46]}")
            self.status.setStyleSheet(f"color:{theme.GREEN};")
        else:
            self.status.setText(f"尚未连接 · 本地端口 {self.port}")
            self.status.setStyleSheet(f"color:{theme.FAINT};")

    def _open_folder(self) -> None:
        self.extension_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(self.extension_dir))
        )
