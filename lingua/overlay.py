"""Screen region picker and always-on-top subtitle overlay."""

from __future__ import annotations

from PyQt5.QtCore import QPoint, QRect, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import (
    QApplication,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class RegionSelector(QWidget):
    region_selected = pyqtSignal(QRect)
    cancelled = pyqtSignal()

    def __init__(self, prompt: str = "拖动框选视频字幕区域  ·  按 Esc 取消"):
        super().__init__(None)
        self.prompt = prompt
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        self._start: QPoint | None = None
        self._current: QPoint | None = None
        screens = QApplication.screens()
        union = QRect()
        for screen in screens:
            union = union.united(screen.geometry())
        if union.isEmpty():
            union = QRect(0, 0, 1920, 1080)
        self.setGeometry(union)

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(8, 14, 25, 132))

        selection = self._selection_rect()
        if selection is not None and selection.width() > 1 and selection.height() > 1:
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(selection, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.setPen(QPen(QColor("#F25A69"), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(selection.adjusted(1, 1, -1, -1))
            label = f"{selection.width()} × {selection.height()}"
            painter.setFont(QFont("Microsoft YaHei UI", 10))
            metrics = painter.fontMetrics()
            badge = QRect(
                selection.left(),
                max(8, selection.top() - 30),
                metrics.horizontalAdvance(label) + 20,
                24,
            )
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(217, 54, 75, 228))
            painter.drawRoundedRect(badge, 6, 6)
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(badge, Qt.AlignCenter, label)

        banner_width = 480
        banner = QRect(
            int((self.width() - banner_width) / 2),
            26,
            banner_width,
            48,
        )
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(18, 26, 40, 224))
        painter.drawRoundedRect(banner, 12, 12)
        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(QFont("Microsoft YaHei UI", 11))
        painter.drawText(
            banner,
            Qt.AlignCenter,
            self.prompt,
        )

    def _selection_rect(self) -> QRect | None:
        if self._start is None or self._current is None:
            return None
        return QRect(self._start, self._current).normalized()

    def mousePressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.button() == Qt.LeftButton:
            self._start = event.pos()
            self._current = event.pos()
            self.update()

    def mouseMoveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self._start is not None:
            self._current = event.pos()
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.button() != Qt.LeftButton or self._start is None:
            return
        selection = self._selection_rect()
        self._start = None
        self._current = None
        if selection is None or selection.width() < 80 or selection.height() < 22:
            self.update()
            return
        global_rect = QRect(
            self.mapToGlobal(selection.topLeft()),
            selection.size(),
        )
        self.hide()
        self.region_selected.emit(global_rect)
        self.close()

    def keyPressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.key() == Qt.Key_Escape:
            self.cancelled.emit()
            self.close()
        else:
            super().keyPressEvent(event)


class SubtitleOverlay(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowTitle("羽中纯声悬浮字幕")
        self.setFixedSize(960, 180)
        self.setWindowOpacity(0.97)
        self._drag_offset: QPoint | None = None
        self.source_label = QLabel("等待字幕…")
        self.source_label.setAlignment(Qt.AlignCenter)
        self.source_label.setWordWrap(True)
        self.source_label.setStyleSheet(
            "color:#AFC0D8;font-size:12px;background:transparent;"
        )
        self.translation_label = QLabel("框选字幕区域后开始识别")
        self.translation_label.setAlignment(Qt.AlignCenter)
        self.translation_label.setWordWrap(True)
        self.translation_label.setStyleSheet(
            "color:#FFFFFF;font-size:23px;font-weight:600;background:transparent;"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(5)
        layout.addWidget(self.source_label)
        layout.addWidget(self.translation_label, 1)

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(255, 255, 255, 34), 1))
        painter.setBrush(QColor(12, 18, 30, 224))
        painter.drawRoundedRect(QRectF(1, 1, self.width() - 2, self.height() - 2), 16, 16)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 80))
        for index in (-1, 0, 1):
            painter.drawEllipse(QRectF(self.width() / 2 + index * 10 - 2, 8, 4, 4))

    def set_content(self, source: str, translation: str) -> None:
        self.source_label.setText(source.strip())
        self.translation_label.setText(translation.strip())

    def place_away_from(self, region: QRect) -> None:
        screen = QApplication.screenAt(region.center()) or QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        width = min(1080, max(620, int(area.width() * 0.72)))
        self.resize(width, 180)
        x = area.x() + int((area.width() - width) / 2)
        if region.center().y() > area.center().y():
            y = area.y() + 34
        else:
            y = area.y() + area.height() - self.height() - 42
        self.move(x, max(area.y(), y))

    def place_default(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        width = min(1080, max(620, int(area.width() * 0.72)))
        self.resize(width, 180)
        self.move(
            area.x() + int((area.width() - width) / 2),
            area.y() + area.height() - self.height() - 74,
        )

    def mousePressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._drag_offset = None
        event.accept()

