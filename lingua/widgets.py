"""Custom painted widgets used by the Yuzhong Chunsheng interface."""

from __future__ import annotations

import math

from PyQt5.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt5.QtGui import (
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt5.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from . import theme
from .branding import draw_brand_mark


def add_shadow(widget: QWidget, blur: int = 30, y_offset: int = 7, alpha: int = 22) -> None:
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, y_offset)
    shadow.setColor(QColor(72, 35, 40, alpha))
    widget.setGraphicsEffect(shadow)


class Card(QFrame):
    def __init__(self, parent: QWidget | None = None, result: bool = False):
        super().__init__(parent)
        self.setObjectName("ResultCard" if result else "Card")
        add_shadow(self, 26, 6, 18)


class LogoMark(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(46, 46)

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        draw_brand_mark(painter, self.width())


class LineIconButton(QPushButton):
    """A compact line-icon button painted with QPainter."""

    def __init__(
        self,
        kind: str,
        tooltip: str = "",
        parent: QWidget | None = None,
        size: int = 34,
    ):
        super().__init__(parent)
        self.kind = kind
        self.setObjectName("IconButton")
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        if tooltip:
            self.setToolTip(tooltip)

    def sizeHint(self) -> QSize:
        return QSize(self.width(), self.height())

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        color = QColor(theme.MUTED if self.isEnabled() else "#B5BECB")
        pen = QPen(color, 1.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        cx = self.width() / 2
        cy = self.height() / 2
        painter.translate(cx - 9, cy - 9)

        if self.kind == "settings":
            for y, knob_x in ((3, 12), (9, 6), (15, 13)):
                painter.drawLine(QPointF(1, y), QPointF(17, y))
                painter.setBrush(QColor(theme.CARD))
                painter.drawEllipse(QPointF(knob_x, y), 2.2, 2.2)
                painter.setBrush(Qt.NoBrush)
        elif self.kind == "copy":
            painter.drawRoundedRect(QRectF(6, 6, 9, 10), 2, 2)
            painter.drawPolyline(
                QPointF(3, 12),
                QPointF(3, 3),
                QPointF(12, 3),
                QPointF(12, 5),
            )
        elif self.kind == "speaker":
            path = QPainterPath()
            path.moveTo(2, 7)
            path.lineTo(5, 7)
            path.lineTo(9, 3)
            path.lineTo(9, 15)
            path.lineTo(5, 11)
            path.lineTo(2, 11)
            path.closeSubpath()
            painter.drawPath(path)
            painter.drawArc(QRectF(8, 4, 7, 10), -55 * 16, 110 * 16)
            painter.drawArc(QRectF(9, 1, 10, 16), -50 * 16, 100 * 16)
        elif self.kind == "swap":
            painter.drawLine(QPointF(2, 6), QPointF(16, 6))
            painter.drawLine(QPointF(13, 3), QPointF(16, 6))
            painter.drawLine(QPointF(13, 9), QPointF(16, 6))
            painter.drawLine(QPointF(16, 12), QPointF(2, 12))
            painter.drawLine(QPointF(5, 9), QPointF(2, 12))
            painter.drawLine(QPointF(5, 15), QPointF(2, 12))
        elif self.kind == "clear":
            painter.drawLine(QPointF(5, 5), QPointF(13, 13))
            painter.drawLine(QPointF(13, 5), QPointF(5, 13))
        elif self.kind == "paste":
            painter.drawRoundedRect(QRectF(4, 3, 10, 14), 2, 2)
            painter.drawRoundedRect(QRectF(7, 1, 4, 4), 1.5, 1.5)
            painter.drawLine(QPointF(7, 8), QPointF(11, 8))
            painter.drawLine(QPointF(7, 11), QPointF(11, 11))
        elif self.kind == "stop":
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(5, 5, 8, 8), 1.5, 1.5)
        elif self.kind == "close":
            painter.drawLine(QPointF(4, 4), QPointF(14, 14))
            painter.drawLine(QPointF(14, 4), QPointF(4, 14))


class SegmentedControl(QWidget):
    currentChanged = pyqtSignal(int)

    def __init__(self, labels: list[str], parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("ModeSwitch")
        self.setFixedHeight(42)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self._buttons: list[QPushButton] = []
        for index, label in enumerate(labels):
            button = QPushButton(label)
            button.setObjectName("ModeButton")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.setMinimumWidth(104)
            self.group.addButton(button, index)
            self._buttons.append(button)
            layout.addWidget(button)
        self._buttons[0].setChecked(True)
        self.group.idClicked.connect(self.currentChanged.emit)

    def setCurrentIndex(self, index: int) -> None:
        if 0 <= index < len(self._buttons):
            self._buttons[index].setChecked(True)

    def currentIndex(self) -> int:
        return self.group.checkedId()


class MicButton(QPushButton):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(126, 126)
        self.setCursor(Qt.PointingHandCursor)
        self._listening = False
        self._busy = False
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(32)
        self._timer.timeout.connect(self._tick)
        self.setToolTip("点击开始语音识别")

    def set_listening(self, listening: bool) -> None:
        self._listening = listening
        self._busy = False
        self.setToolTip("点击停止聆听" if listening else "点击开始语音识别")
        if listening:
            self._timer.start()
        else:
            self._timer.stop()
            self._phase = 0.0
        self.update()

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.setEnabled(not busy)
        if busy:
            self._timer.stop()
        self.update()

    def _tick(self) -> None:
        self._phase += 0.09
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(3, 3, 120, 120)

        if self._listening:
            for index, radius in enumerate((61, 57, 53)):
                pulse = (math.sin(self._phase * 2.0 - index * 0.8) + 1.0) / 2.0
                alpha = int(42 + 42 * pulse)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(217, 54, 75, alpha))
                painter.drawEllipse(rect.center(), radius + 1, radius + 1)

        painter.setPen(QPen(QColor("#F1D7DC"), 1))
        painter.setBrush(QColor("#FFF7F5"))
        painter.drawEllipse(rect)

        inner = QRectF(13, 13, 100, 100)
        if self._busy:
            gradient = QLinearGradient(inner.topLeft(), inner.bottomRight())
            gradient.setColorAt(0, QColor("#B9C7DB"))
            gradient.setColorAt(1, QColor("#9CACBF"))
        elif self._listening:
            gradient = QLinearGradient(inner.topLeft(), inner.bottomRight())
            gradient.setColorAt(0, QColor("#EB5C69"))
            gradient.setColorAt(0.55, QColor("#D9364B"))
            gradient.setColorAt(1, QColor("#B41D34"))
        else:
            gradient = QLinearGradient(inner.topLeft(), inner.bottomRight())
            gradient.setColorAt(0, QColor("#E34A5A"))
            gradient.setColorAt(1, QColor("#BB2038"))
        painter.setPen(Qt.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(inner)

        painter.setPen(
            QPen(
                QColor("#FFFFFF"),
                4.0,
                Qt.SolidLine,
                Qt.RoundCap,
                Qt.RoundJoin,
            )
        )
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(QRectF(55, 36, 16, 31), 8, 8)
        path = QPainterPath()
        path.moveTo(45, 59)
        path.cubicTo(45, 74, 55, 81, 63, 81)
        path.cubicTo(71, 81, 81, 74, 81, 59)
        painter.drawPath(path)
        painter.drawLine(QPointF(63, 81), QPointF(63, 91))
        painter.drawLine(QPointF(52, 92), QPointF(74, 92))


class WaveformWidget(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumWidth(280)
        self.setFixedHeight(32)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._active = False
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)

    def set_active(self, active: bool) -> None:
        self._active = active
        if active:
            self._timer.start()
        else:
            self._timer.stop()
            self._phase = 0.0
        self.update()

    def _tick(self) -> None:
        self._phase += 0.16
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        available = max(20, self.width() - 18)
        bars = max(9, available // 11)
        gap = available / bars
        bar_width = 3.2
        center_y = self.height() / 2
        for index in range(bars):
            if self._active:
                envelope = 0.45 + 0.55 * math.sin(
                    math.pi * (index + 1) / (bars + 1)
                )
                wave = abs(math.sin(self._phase + index * 0.58))
                height = 4 + 22 * envelope * (0.18 + 0.82 * wave)
                alpha = 90 + int(70 * envelope)
            else:
                wave = abs(math.sin(index * 0.68))
                height = 3 + 5 * wave
                alpha = 60
            x = 9 + index * gap + (gap - bar_width) / 2
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(217, 54, 75, alpha))
            painter.drawRoundedRect(
                QRectF(x, center_y - height / 2, bar_width, height),
                1.6,
                1.6,
            )


class Toast(QFrame):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setProperty("kind", "info")
        self.setVisible(False)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(17, 10, 17, 10)
        self.label = QLabel()
        self.label.setObjectName("ToastText")
        self.label.setWordWrap(True)
        layout.addWidget(self.label)
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._fade = QPropertyAnimation(self._effect, b"opacity", self)
        self._fade.setEasingCurve(QEasingCurve.OutCubic)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._fade_out)

    def show_message(self, message: str, kind: str = "info", duration: int = 2800) -> None:
        self._fade.stop()
        self._hide_timer.stop()
        self.label.setText(message)
        self.setProperty("kind", kind)
        self.style().unpolish(self)
        self.style().polish(self)
        self.adjustSize()
        width = min(620, max(260, self.sizeHint().width()))
        self.setFixedWidth(width)
        self.adjustSize()
        parent_rect = self.parentWidget().rect()
        x = int((parent_rect.width() - self.width()) / 2)
        y = max(20, parent_rect.height() - self.height() - 34)
        self.move(x, y)
        self._effect.setOpacity(0.0)
        self.show()
        self.raise_()
        self._fade.setDuration(150)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()
        self._hide_timer.start(duration)

    def _fade_out(self) -> None:
        self._fade.stop()
        self._fade.setDuration(220)
        self._fade.setStartValue(self._effect.opacity())
        self._fade.setEndValue(0.0)
        self._fade.finished.connect(self.hide)
        self._fade.start()

