"""Always-on-top floating launcher and its compact action panel."""

from __future__ import annotations

from PyQt5.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QMouseEvent, QPainter, QPen
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .branding import draw_brand_mark


class FloatingLauncher(QWidget):
    clicked = pyqtSignal()
    double_clicked = pyqtSignal()
    position_changed = pyqtSignal(QPoint)

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(62, 62)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("羽中纯声快捷功能")
        self._press_global: QPoint | None = None
        self._drag_origin: QPoint | None = None
        self._dragged = False
        self._hovered = False
        self._active = False

    def set_active(self, active: bool) -> None:
        if self._active == active:
            return
        self._active = active
        self.setToolTip(
            "羽中纯声 · 正在识别" if active else "羽中纯声快捷功能"
        )
        self.update()

    def place_default(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        self.move(
            area.right() - self.width() - 26,
            area.top() + int(area.height() * 0.42),
        )

    def clamp_to_screen(self) -> None:
        screen = QApplication.screenAt(self.frameGeometry().center())
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        x = min(max(self.x(), area.left() + 6), area.right() - self.width() - 6)
        y = min(max(self.y(), area.top() + 6), area.bottom() - self.height() - 6)
        self.move(x, y)

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(
            QPen(
                QColor(255, 255, 255, 210 if self._hovered else 150),
                2,
            )
        )
        painter.setBrush(QColor(45, 28, 31, 55))
        painter.drawEllipse(1, 1, self.width() - 2, self.height() - 2)
        painter.translate(8, 8)
        draw_brand_mark(painter, 46)
        if self._active:
            painter.resetTransform()
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.GREEN))
            painter.drawEllipse(self.width() - 16, 7, 10, 10)

    def enterEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._press_global = event.globalPos()
            self._drag_origin = self.pos()
            self._dragged = False
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (
            self._press_global is not None
            and self._drag_origin is not None
            and event.buttons() & Qt.LeftButton
        ):
            delta = event.globalPos() - self._press_global
            if delta.manhattanLength() >= 4:
                self._dragged = True
            if self._dragged:
                self.move(self._drag_origin + delta)
                event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.LeftButton:
            return
        dragged = self._dragged
        self._press_global = None
        self._drag_origin = None
        self._dragged = False
        if dragged:
            self.clamp_to_screen()
            self.position_changed.emit(self.pos())
        else:
            self.clicked.emit()
        event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit()
            event.accept()


class QuickActionPanel(QWidget):
    action_requested = pyqtSignal(str)

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.Popup | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(276)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        card = QFrame()
        card.setObjectName("QuickCard")
        card.setStyleSheet(
            "QFrame#QuickCard{background:rgba(255,252,251,248);"
            f"border:1px solid {theme.BORDER};border-radius:16px;}}"
            "QLabel{background:transparent;}"
            "QPushButton{border:none;border-radius:9px;padding:8px 10px;"
            "text-align:left;color:#352B2D;background:transparent;}"
            "QPushButton:hover{background:#FAE9EC;color:#9F1D32;}"
            "QPushButton:disabled{color:#B8ADAF;}"
            "QPushButton#OpenMain{background:#D9364B;color:white;"
            "font-weight:600;text-align:center;padding:10px;}"
            "QPushButton#OpenMain:hover{background:#BE263D;color:white;}"
            "QPushButton#HideButton{color:#9B8F91;font-size:11px;}"
            "QPushButton#ExitButton{color:#B72F3C;font-size:11px;}"
            "QPushButton#ExitButton:hover{background:#FFF0F1;color:#A5152B;}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 10)
        layout.setSpacing(2)
        root.addWidget(card)

        header = QHBoxLayout()
        title = QLabel("羽中纯声")
        title.setStyleSheet("font-size:15px;font-weight:700;color:#322527;")
        self.state_label = QLabel("待命")
        self.state_label.setStyleSheet(
            f"color:{theme.FAINT};font-size:10px;background:#F7F1F1;"
            "border-radius:7px;padding:2px 7px;"
        )
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.state_label)
        layout.addLayout(header)

        self.open_main = QPushButton("打开主窗口")
        self.open_main.setObjectName("OpenMain")
        self.open_main.clicked.connect(lambda: self._emit("open"))
        layout.addWidget(self.open_main)

        layout.addWidget(self._separator())
        self._button(layout, "文字翻译", "text")
        self._button(layout, "语音翻译", "voice")
        self._button(layout, "视频辅助", "video")
        self._button(layout, "播放器时间同步", "sync")
        layout.addWidget(self._separator())
        self._button(layout, "选区翻译    Ctrl+Alt+T", "quick")
        self.audio_button = self._button(
            layout,
            "开始电脑声音识别",
            "audio",
        )
        self.subtitle_button = self._button(
            layout,
            "开始画面字幕识别",
            "subtitle",
        )
        self.summary_button = self._button(
            layout,
            "打开视频总结",
            "summary",
        )
        layout.addWidget(self._separator())
        hide_button = QPushButton("隐藏漂浮按钮（可在主窗口重新显示）")
        hide_button.setObjectName("HideButton")
        hide_button.clicked.connect(lambda: self._emit("hide"))
        layout.addWidget(hide_button)
        exit_button = QPushButton("彻底退出羽中纯声")
        exit_button.setObjectName("ExitButton")
        exit_button.clicked.connect(lambda: self._emit("quit"))
        layout.addWidget(exit_button)

    def _button(
        self,
        layout: QVBoxLayout,
        text: str,
        action: str,
    ) -> QPushButton:
        button = QPushButton(text)
        button.clicked.connect(lambda: self._emit(action))
        layout.addWidget(button)
        return button

    @staticmethod
    def _separator() -> QFrame:
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background:{theme.BORDER};border:none;")
        return line

    def _emit(self, action: str) -> None:
        self.hide()
        self.action_requested.emit(action)

    def set_state(
        self,
        monitoring: bool,
        source: str,
        has_subtitle_region: bool,
        has_video_entries: bool,
    ) -> None:
        if monitoring and source == "audio":
            self.state_label.setText("声音识别中")
            self.audio_button.setText("停止电脑声音识别")
        elif monitoring and source == "subtitle":
            self.state_label.setText("字幕识别中")
            self.audio_button.setText("切换到电脑声音识别")
        else:
            self.state_label.setText("待命")
            self.audio_button.setText("开始电脑声音识别")
        if monitoring and source == "subtitle":
            self.subtitle_button.setText("停止画面字幕识别")
        elif has_subtitle_region:
            self.subtitle_button.setText(
                "切换到画面字幕识别"
                if monitoring
                else "开始画面字幕识别"
            )
        else:
            self.subtitle_button.setText("选择画面字幕区域")
        self.summary_button.setEnabled(has_video_entries)
        self.adjustSize()

    def show_near(self, anchor: QWidget) -> None:
        self.adjustSize()
        area = QApplication.screenAt(anchor.frameGeometry().center())
        if area is None:
            area = QApplication.primaryScreen()
        available = area.availableGeometry() if area is not None else QRect()
        x = anchor.x() - self.width() - 10
        if x < available.left() + 8:
            x = anchor.x() + anchor.width() + 10
        y = anchor.y() + int((anchor.height() - self.height()) / 2)
        if available.isValid():
            x = max(available.left() + 8, min(x, available.right() - self.width() - 8))
            y = max(available.top() + 8, min(y, available.bottom() - self.height() - 8))
        self.move(x, y)
        self.show()
        self.raise_()

    def keyPressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.key() == Qt.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)
