"""Feather and sound-wave brand artwork."""

from __future__ import annotations

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)


BRAND_RED = "#D92F45"
BRAND_RED_DARK = "#A80F27"
BRAND_CREAM = "#FFF7ED"


def draw_brand_mark(painter: QPainter, size: int) -> None:
    """Draw the brand at any resolution using a 64-unit design grid."""
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    scale = size / 64.0
    painter.scale(scale, scale)

    background = QLinearGradient(6, 4, 59, 62)
    background.setColorAt(0.0, QColor("#F0555E"))
    background.setColorAt(0.5, QColor(BRAND_RED))
    background.setColorAt(1.0, QColor(BRAND_RED_DARK))
    painter.setPen(Qt.NoPen)
    painter.setBrush(background)
    painter.drawRoundedRect(QRectF(1, 1, 62, 62), 17, 17)

    painter.setBrush(Qt.NoBrush)
    painter.setPen(QPen(QColor(255, 255, 255, 28), 0.9))
    painter.drawRoundedRect(QRectF(2.3, 2.3, 59.4, 59.4), 15.6, 15.6)

    feather = QPainterPath()
    feather.moveTo(11.5, 51.5)
    feather.cubicTo(15.5, 37.0, 26.5, 17.0, 43.5, 9.0)
    feather.cubicTo(44.0, 24.5, 36.5, 41.5, 19.0, 52.0)
    feather.cubicTo(16.2, 53.5, 13.0, 53.2, 11.5, 51.5)
    feather.closeSubpath()
    feather_fill = QLinearGradient(14, 12, 36, 49)
    feather_fill.setColorAt(0.0, QColor("#FFFFFF"))
    feather_fill.setColorAt(1.0, QColor(BRAND_CREAM))
    painter.setPen(Qt.NoPen)
    painter.setBrush(feather_fill)
    painter.drawPath(feather)

    painter.setPen(
        QPen(QColor("#D52A42"), 1.15, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    )
    shaft = QPainterPath()
    shaft.moveTo(13.0, 50.5)
    shaft.cubicTo(21.0, 41.0, 32.0, 23.0, 40.5, 13.0)
    painter.drawPath(shaft)

    painter.setPen(QPen(QColor(217, 47, 69, 205), 0.9, Qt.SolidLine, Qt.RoundCap))
    for start, end in (
        ((20.5, 41.0), (27.0, 35.5)),
        ((24.5, 34.0), (31.0, 28.8)),
        ((29.0, 26.5), (35.0, 21.7)),
    ):
        painter.drawLine(QPointF(*start), QPointF(*end))

    painter.setPen(
        QPen(QColor(255, 255, 255, 235), 2.0, Qt.SolidLine, Qt.RoundCap)
    )
    inner_wave = QPainterPath()
    inner_wave.moveTo(48.0, 34.0)
    inner_wave.cubicTo(51.8, 37.3, 51.8, 44.7, 48.0, 48.0)
    painter.drawPath(inner_wave)

    painter.setPen(
        QPen(QColor(255, 255, 255, 155), 2.0, Qt.SolidLine, Qt.RoundCap)
    )
    outer_wave = QPainterPath()
    outer_wave.moveTo(53.0, 29.0)
    outer_wave.cubicTo(58.8, 34.5, 58.8, 47.5, 53.0, 53.0)
    painter.drawPath(outer_wave)
    painter.restore()


def make_brand_icon(size: int = 256) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    draw_brand_mark(painter, size)
    painter.end()
    return QIcon(pixmap)


def make_brand_pixmap(size: int = 256) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    draw_brand_mark(painter, size)
    painter.end()
    return pixmap

