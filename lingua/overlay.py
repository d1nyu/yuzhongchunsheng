"""Screen region picker and always-on-top subtitle overlay."""

from __future__ import annotations

from PyQt5.QtCore import QPoint, QRect, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class RegionSelector(QWidget):
    region_selected = pyqtSignal(QRect)
    cancelled = pyqtSignal()

    def __init__(
        self,
        prompt: str = "拖动框选视频字幕区域  ·  按 Esc 取消",
        min_width: int = 80,
        min_height: int = 22,
    ):
        super().__init__(None)
        self.prompt = prompt
        self.min_width = min_width
        self.min_height = min_height
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
        if (
            selection is None
            or selection.width() < self.min_width
            or selection.height() < self.min_height
        ):
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
    close_requested = pyqtSignal()

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
        self.setFixedSize(960, 210)
        self.setWindowOpacity(0.97)
        self._drag_offset: QPoint | None = None
        self.close_button = QPushButton("×", self)
        self.close_button.setFixedSize(28, 28)
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.setToolTip("停止识别并关闭悬浮字幕")
        self.close_button.setStyleSheet(
            "QPushButton{background:rgba(255,255,255,18);color:#E8EEF8;"
            "border:none;border-radius:8px;font-size:18px;padding:0;}"
            "QPushButton:hover{background:rgba(255,255,255,42);color:#FFFFFF;}"
            "QPushButton:pressed{background:rgba(255,255,255,62);}"
        )
        self.close_button.clicked.connect(self.close_requested.emit)
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
            "color:#FFFFFF;font-size:18px;font-weight:600;background:transparent;"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(5)
        layout.addWidget(self.source_label)
        layout.addWidget(self.translation_label, 1)

    def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().resizeEvent(event)
        self.close_button.move(self.width() - 38, 10)
        self.close_button.raise_()

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

    def set_entries(self, entries: list[tuple[str, str, str]]) -> None:
        sources: list[str] = []
        translations: list[str] = []
        for speaker, source, translation in entries[-3:]:
            prefix = f"{speaker.strip()}：" if speaker.strip() else ""
            sources.append(prefix + source.strip())
            translations.append(prefix + translation.strip())
        self.source_label.setText("\n".join(sources))
        self.translation_label.setText("\n".join(translations))

    def place_away_from(self, region: QRect) -> None:
        screen = QApplication.screenAt(region.center()) or QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        width = min(1080, max(620, int(area.width() * 0.72)))
        self.resize(width, 210)
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
        self.resize(width, 210)
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


class QuickTranslationPopup(QWidget):
    """Floating result card for screen-selection translation."""

    speak_requested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("羽中纯声 · 选区翻译")
        self.setFixedSize(570, 350)
        self._drag_offset: QPoint | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 17, 22, 17)
        root.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(8)
        title = QLabel("选区翻译")
        title.setStyleSheet(
            "font-size:14px;font-weight:700;color:#AD1D33;background:transparent;"
        )
        title.setAttribute(Qt.WA_TransparentForMouseEvents)
        header.addWidget(title)
        self.provider = QLabel("")
        self.provider.setObjectName("ProviderBadge")
        header.addWidget(self.provider)
        header.addStretch()
        close_button = QPushButton("×")
        close_button.setObjectName("GhostButton")
        close_button.setFixedSize(30, 30)
        close_button.setToolTip("关闭")
        close_button.clicked.connect(self.close)
        header.addWidget(close_button)
        root.addLayout(header)

        source_title = QLabel("原文")
        source_title.setObjectName("Faint")
        root.addWidget(source_title)
        self.source_edit = QTextEdit()
        self.source_edit.setReadOnly(True)
        self.source_edit.setAcceptRichText(False)
        self.source_edit.setFixedHeight(58)
        self.source_edit.setPlaceholderText("正在识别…")
        self.source_edit.setStyleSheet(
            "QTextEdit{background:rgba(255,247,245,205);border:1px solid rgba(242,222,225,220);"
            "border-radius:9px;padding:7px;color:#786D6F;font-size:12px;}"
        )
        root.addWidget(self.source_edit)

        result_title = QLabel("译文")
        result_title.setObjectName("Faint")
        root.addWidget(result_title)
        self.result_edit = QTextEdit()
        self.result_edit.setReadOnly(True)
        self.result_edit.setAcceptRichText(False)
        self.result_edit.setPlaceholderText("翻译结果会显示在这里")
        self.result_edit.setStyleSheet(
            "QTextEdit{background:rgba(255,255,255,195);border:1px solid rgba(240,215,220,220);"
            "border-radius:10px;padding:10px;color:#3B2428;font-size:17px;}"
        )
        root.addWidget(self.result_edit, 1)

        footer = QHBoxLayout()
        self.status = QLabel("正在识别选区文字…")
        self.status.setObjectName("Faint")
        footer.addWidget(self.status)
        footer.addStretch()
        self.copy_button = QPushButton("复制")
        self.copy_button.setObjectName("SecondaryButton")
        self.copy_button.clicked.connect(self._copy)
        footer.addWidget(self.copy_button)
        self.speak_button = QPushButton("朗读")
        self.speak_button.setObjectName("SecondaryButton")
        self.speak_button.clicked.connect(self._speak)
        footer.addWidget(self.speak_button)
        root.addLayout(footer)

    def show_for_region(self, region: QRect) -> None:
        screen = QApplication.screenAt(region.center()) or QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            x = max(
                area.left() + 12,
                min(
                    region.center().x() - self.width() // 2,
                    area.right() - self.width() - 12,
                ),
            )
            gap = 14
            below = region.bottom() + gap
            above = region.top() - self.height() - gap
            if below + self.height() <= area.bottom() - 12:
                y = below
            elif above >= area.top() + 12:
                y = above
            else:
                y = max(
                    area.top() + 12,
                    min(
                        region.center().y() - self.height() // 2,
                        area.bottom() - self.height() - 12,
                    ),
                )
            self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()

    def set_content(
        self,
        source: str,
        translation: str,
        status: str,
        provider: str = "",
    ) -> None:
        self.source_edit.setPlainText(source.strip())
        self.result_edit.setPlainText(translation.strip())
        self.status.setText(status)
        self.provider.setText(provider)
        self.provider.setVisible(bool(provider))

    def set_error(self, message: str) -> None:
        self.status.setText(message)
        self.result_edit.setPlainText("翻译失败")
        self.provider.setVisible(False)

    def _copy(self) -> None:
        text = self.result_edit.toPlainText().strip()
        if not text:
            return
        QApplication.clipboard().setText(text)
        self.status.setText("译文已复制")

    def _speak(self) -> None:
        text = self.result_edit.toPlainText().strip()
        if text:
            self.speak_requested.emit(text)

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(238, 215, 219, 210), 1))
        painter.setBrush(QColor(255, 252, 251, 218))
        painter.drawRoundedRect(
            QRectF(1, 1, self.width() - 2, self.height() - 2),
            18,
            18,
        )
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#D9364B"))
        painter.drawRoundedRect(QRectF(1, 1, self.width() - 2, 4), 2, 2)

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

    def keyPressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

