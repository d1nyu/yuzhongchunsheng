"""Local OCR for screen-captured video subtitles."""

from __future__ import annotations

import queue
import re
from dataclasses import dataclass
from typing import Any

import numpy as np
from PyQt5.QtCore import QThread, Qt, pyqtSignal
from PyQt5.QtGui import QImage


def qimage_to_numpy(image: QImage) -> np.ndarray | None:
    if image.isNull():
        return None
    image = image.convertToFormat(QImage.Format_RGB888)
    width = image.width()
    height = image.height()
    if width <= 0 or height <= 0:
        return None
    pointer = image.bits()
    pointer.setsize(image.byteCount())
    data = np.frombuffer(pointer, dtype=np.uint8)
    stride = image.bytesPerLine()
    data = data.reshape((height, stride))[:, : width * 3]
    return data.reshape((height, width, 3)).copy()


@dataclass
class _OcrLine:
    text: str
    x: float
    center_y: float
    height: float


def _join_fragments(fragments: list[str]) -> str:
    result = ""
    for fragment in fragments:
        fragment = fragment.strip()
        if not fragment:
            continue
        if not result:
            result = fragment
            continue
        previous = result[-1]
        current = fragment[0]
        if (
            "\u4e00" <= previous <= "\u9fff"
            and "\u4e00" <= current <= "\u9fff"
        ):
            result += fragment
        else:
            result += " " + fragment
    return re.sub(r"[ \t]+", " ", result).strip()


def combine_ocr_lines(result: Any) -> str:
    """Merge RapidOCR boxes into at most three natural subtitle lines."""
    if not result:
        return ""
    entries: list[_OcrLine] = []
    for item in result:
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            continue
        box, text, score = item[0], item[1], item[2]
        try:
            confidence = float(score)
        except (TypeError, ValueError):
            continue
        if confidence < 0.24 or not isinstance(text, str) or not text.strip():
            continue
        try:
            xs = [float(point[0]) for point in box]
            ys = [float(point[1]) for point in box]
        except (TypeError, ValueError, IndexError):
            continue
        if not xs or not ys:
            continue
        entries.append(
            _OcrLine(
                text=" ".join(text.split()),
                x=min(xs),
                center_y=(min(ys) + max(ys)) / 2,
                height=max(2.0, max(ys) - min(ys)),
            )
        )
    entries.sort(key=lambda entry: (entry.center_y, entry.x))
    grouped: list[list[_OcrLine]] = []
    for entry in entries:
        placed = False
        for group in grouped:
            reference = group[0]
            tolerance = max(9.0, min(24.0, max(reference.height, entry.height) * 0.62))
            if abs(entry.center_y - reference.center_y) <= tolerance:
                group.append(entry)
                placed = True
                break
        if not placed:
            grouped.append([entry])
    grouped.sort(key=lambda group: min(item.center_y for item in group))
    lines: list[str] = []
    for group in grouped[:3]:
        group.sort(key=lambda entry: entry.x)
        line = _join_fragments([entry.text for entry in group])
        if line and (not lines or line != lines[-1]):
            lines.append(line)
    return "\n".join(lines).strip()


class SubtitleOcrWorker(QThread):
    text_ready = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue: queue.Queue[np.ndarray | None] = queue.Queue(maxsize=1)
        self._stopping = False

    def submit(self, image: QImage) -> None:
        if not image.isNull() and (image.width() < 320 or image.height() < 80):
            factor = min(
                6.0,
                max(
                    2.0,
                    min(
                        320.0 / max(1, image.width()),
                        80.0 / max(1, image.height()),
                    ),
                ),
            )
            image = image.scaled(
                max(1, int(image.width() * factor)),
                max(1, int(image.height() * factor)),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        array = qimage_to_numpy(image)
        if array is None or self._stopping:
            return
        try:
            self._queue.put_nowait(array)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(array)
            except queue.Full:
                pass

    def run(self) -> None:
        try:
            from rapidocr_onnxruntime import RapidOCR

            engine = RapidOCR()
        except Exception as exc:
            self.error.emit(f"无法启动本地 OCR：{exc}")
            return

        while not self._stopping:
            try:
                item = self._queue.get(timeout=0.25)
            except queue.Empty:
                continue
            if item is None:
                break
            try:
                result, _ = engine(item, use_det=True, use_cls=False, use_rec=True)
                text = combine_ocr_lines(result)
                self.text_ready.emit(text)
            except Exception as exc:
                self.error.emit(f"字幕识别失败：{exc}")

    def stop(self) -> None:
        self._stopping = True
        try:
            self._queue.get_nowait()
        except queue.Empty:
            pass
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass

