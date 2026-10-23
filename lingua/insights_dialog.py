"""Non-modal video analysis and follow-up window."""

from __future__ import annotations

import html
import re
from urllib.parse import unquote

from PyQt5.QtCore import QUrl, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .video_insights import format_timestamp


class VideoAssistantDialog(QDialog):
    summarize_requested = pyqtSignal()
    question_requested = pyqtSignal(str)
    time_clicked = pyqtSignal(float)
    seek_requested = pyqtSignal(float)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("羽中纯声 · 视频理解")
        self.setModal(False)
        self.resize(790, 690)
        self.setMinimumSize(680, 570)
        self._content: list[str] = []
        self._busy = False
        self._build_ui()
        self._render()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(11)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("视频理解")
        title.setObjectName("PageTitle")
        subtitle = QLabel("根据本次播放的对话生成总结，也可以继续追问")
        subtitle.setObjectName("Muted")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()
        self.provider = QLabel("DeepSeek")
        self.provider.setObjectName("ProviderBadge")
        header.addWidget(self.provider)
        close_button = QPushButton("×")
        close_button.setObjectName("GhostButton")
        close_button.setFixedSize(30, 30)
        close_button.setToolTip("关闭视频理解")
        close_button.clicked.connect(self.close)
        header.addWidget(close_button)
        root.addLayout(header)

        meta_row = QHBoxLayout()
        self.record_label = QLabel("还没有可分析的对话")
        self.record_label.setObjectName("Faint")
        meta_row.addWidget(self.record_label)
        meta_row.addStretch()
        self.status = QLabel("识别视频后即可生成总结")
        self.status.setObjectName("Muted")
        meta_row.addWidget(self.status)
        root.addLayout(meta_row)

        self.browser = QTextBrowser()
        self.browser.setOpenLinks(False)
        self.browser.anchorClicked.connect(self._anchor_clicked)
        self.browser.setStyleSheet(
            "QTextBrowser{background:#FFFFFF;border:1px solid "
            f"{theme.BORDER};border-radius:14px;padding:16px;"
            "color:#31282A;font-size:14px;}"
        )
        root.addWidget(self.browser, 1)

        quick = QHBoxLayout()
        quick.setSpacing(6)
        self._quick_buttons: list[QPushButton] = []
        for label, question, width in (
            ("总结目前", "", 78),
            ("刚才讲了什么", "刚才讲了什么？请重点说明最近的内容。", 110),
            ("最近五分钟", "请总结最近五分钟的内容。", 94),
            ("人物观点", "请按说话人整理各自的观点、依据和分歧。", 82),
            ("决定与待办", "请找出视频中明确的决定、承诺和待办事项。", 94),
        ):
            button = QPushButton(label)
            button.setObjectName("SecondaryButton")
            button.setMinimumWidth(width)
            if question:
                button.clicked.connect(
                    lambda checked=False, value=question: self._ask(value)
                )
            else:
                button.clicked.connect(self.summarize_requested.emit)
            quick.addWidget(button)
            self._quick_buttons.append(button)
        quick.addStretch()
        root.addLayout(quick)

        ask_row = QHBoxLayout()
        ask_row.setSpacing(8)
        self.question_edit = QLineEdit()
        self.question_edit.setPlaceholderText("继续追问，例如：他为什么反对这个方案？")
        self.question_edit.returnPressed.connect(self._submit_question)
        ask_row.addWidget(self.question_edit, 1)
        self.ask_button = QPushButton("追问")
        self.ask_button.setObjectName("PrimaryButton")
        self.ask_button.setMinimumWidth(92)
        self.ask_button.clicked.connect(self._submit_question)
        ask_row.addWidget(self.ask_button)
        self.copy_button = QPushButton("复制")
        self.copy_button.setObjectName("SecondaryButton")
        self.copy_button.clicked.connect(self._copy_content)
        ask_row.addWidget(self.copy_button)
        root.addLayout(ask_row)

        self.footer = QLabel(
            "连接浏览器时间同步后，[视频时间] 可点击跳转；"
            "未连接时使用从开始识别计算的[本次播放时间]。"
            "分析只依据本次转写和译文，不会自动判断观点真假。"
        )
        self.footer.setObjectName("Faint")
        self.footer.setWordWrap(True)
        root.addWidget(self.footer)

    def set_session_info(
        self,
        record_count: int,
        duration_seconds: float,
        player_duration: float | None = None,
    ) -> None:
        if record_count <= 0:
            self.record_label.setText("还没有可分析的对话")
        else:
            if player_duration is not None and player_duration > 0:
                duration_text = f"视频约 {format_timestamp(player_duration)}"
            else:
                duration_text = f"本次播放约 {format_timestamp(duration_seconds)}"
            self.record_label.setText(
                f"{record_count} 条对话 · {duration_text}"
            )

    def set_loading(self, message: str = "正在分析本次视频…") -> None:
        self._busy = True
        self.status.setText(message)
        self.status.setStyleSheet(f"color:{theme.ACCENT};")
        self.question_edit.setEnabled(False)
        self.ask_button.setEnabled(False)
        for button in self._quick_buttons:
            button.setEnabled(False)

    def set_summary(self, text: str, provider: str) -> None:
        self._finish_loading()
        self._content = [
            '<div class="answer">' + self._to_html(text) + "</div>"
        ]
        self.provider.setText(provider)
        self.provider.setVisible(bool(provider))
        self.status.setText("总结完成，可以继续追问")
        self.status.setStyleSheet(f"color:{theme.GREEN};")
        self._render()

    def add_exchange(self, question: str, answer: str, provider: str) -> None:
        self._finish_loading()
        self._content.extend(
            [
                '<div class="question"><span>你问</span> '
                + html.escape(question.strip())
                + "</div>",
                '<div class="answer">' + self._to_html(answer) + "</div>",
            ]
        )
        self.provider.setText(provider)
        self.provider.setVisible(bool(provider))
        self.status.setText("回答完成")
        self.status.setStyleSheet(f"color:{theme.GREEN};")
        self._render()

    def add_answer(self, answer: str, provider: str) -> None:
        self._finish_loading()
        self._content.append(
            '<div class="answer">' + self._to_html(answer) + "</div>"
        )
        self.provider.setText(provider)
        self.provider.setVisible(bool(provider))
        self.status.setText("回答完成")
        self.status.setStyleSheet(f"color:{theme.GREEN};")
        self._render()

    def add_question(self, question: str) -> None:
        self._content.append(
            '<div class="question"><span>你问</span> '
            + html.escape(question.strip())
            + "</div>"
        )
        self._render()

    def set_error(self, message: str) -> None:
        self._finish_loading()
        self._content.append(
            '<div class="error">' + html.escape(message.strip()) + "</div>"
        )
        self.status.setText("分析失败")
        self.status.setStyleSheet(f"color:{theme.RED};")
        self._render()

    def show_message(self, message: str) -> None:
        self._content = [
            '<div class="empty">' + html.escape(message.strip()) + "</div>"
        ]
        self._render()

    def _finish_loading(self) -> None:
        self._busy = False
        self.question_edit.setEnabled(True)
        self.ask_button.setEnabled(True)
        for button in self._quick_buttons:
            button.setEnabled(True)

    def _submit_question(self) -> None:
        question = self.question_edit.text().strip()
        if not question:
            return
        self.question_edit.clear()
        self._ask(question)

    def _ask(self, question: str) -> None:
        if self._busy or not question.strip():
            return
        self.question_requested.emit(question.strip())

    def _render(self) -> None:
        body = "\n".join(self._content)
        if not body:
            body = '<div class="empty">识别视频后，这里会自动生成总结。</div>'
        self.browser.setHtml(
            "<html><head><style>"
            "body{font-family:'Microsoft YaHei UI','Segoe UI';line-height:1.6;}"
            ".answer{white-space:pre-wrap;margin:8px 0 20px 0;}"
            "h1,h2,h3{margin:16px 0 7px 0;color:#2C2224;}"
            "h1{font-size:19px;}h2{font-size:17px;}h3{font-size:15px;}"
            ".line{margin:3px 0;}"
            ".bullet{margin:3px 0 3px 5px;}"
            ".gap{height:7px;}"
            ".question{background:#FFF0F3;color:#8D2033;border-radius:9px;"
            "padding:9px 12px;margin:16px 0 8px 0;}"
            ".question span{font-size:11px;font-weight:600;color:#B14A5C;}"
            ".error{background:#FFF2F2;color:#B72F3C;border-radius:9px;"
            "padding:12px;margin:10px 0;}"
            ".empty{color:#9B8E90;text-align:center;padding:46px 12px;}"
            "a{color:#C4253F;text-decoration:none;font-weight:600;}"
            "</style></head><body>"
            f"{body}</body></html>"
        )
        self.browser.verticalScrollBar().setValue(
            self.browser.verticalScrollBar().maximum()
        )

    def _to_html(self, text: str) -> str:
        lines: list[str] = []
        for raw_line in text.strip().splitlines():
            stripped = raw_line.strip()
            if not stripped:
                lines.append('<div class="gap"></div>')
                continue
            heading = re.match(r"^(#{1,3})\s+(.+)$", stripped)
            if heading:
                level = len(heading.group(1))
                lines.append(
                    f"<h{level}>{self._inline(heading.group(2))}</h{level}>"
                )
                continue
            bullet = re.match(r"^[-*•]\s+(.+)$", stripped)
            if bullet:
                lines.append(
                    '<div class="bullet">• '
                    f"{self._inline(bullet.group(1))}</div>"
                )
                continue
            numbered = re.match(r"^(\d+)[.、]\s*(.+)$", stripped)
            if numbered:
                lines.append(
                    '<div class="bullet">'
                    f"{numbered.group(1)}. "
                    f"{self._inline(numbered.group(2))}</div>"
                )
                continue
            lines.append(
                f'<div class="line">{self._inline(stripped)}</div>'
            )
        return "".join(lines)

    def _inline(self, text: str) -> str:
        escaped = html.escape(text)
        escaped = re.sub(
            r"\*\*(.+?)\*\*",
            r"<b>\1</b>",
            escaped,
        )
        timestamp_pattern = re.compile(
            r"\[(视频|本次播放)\s+(\d{1,3}:\d{2}(?::\d{2})?)\]"
        )

        def replace_timestamp(match: re.Match[str]) -> str:
            label = match.group(0)
            kind = match.group(1)
            value = match.group(2)
            parts = [int(part) for part in value.split(":")]
            seconds = (
                parts[0] * 3600 + parts[1] * 60 + parts[2]
                if len(parts) == 3
                else parts[0] * 60 + parts[1]
            )
            scheme = "player-time" if kind == "视频" else "session-time"
            return (
                f'<a href="{scheme}:{seconds}">{html.escape(label)}</a>'
            )

        return timestamp_pattern.sub(replace_timestamp, escaped)

    def _anchor_clicked(self, url: QUrl) -> None:
        value = unquote(url.toString())
        if value.startswith("session-time:"):
            try:
                seconds = float(value.split(":", 1)[1])
            except ValueError:
                return
            self.time_clicked.emit(seconds)
        elif value.startswith("player-time:"):
            try:
                seconds = float(value.split(":", 1)[1])
            except ValueError:
                return
            self.seek_requested.emit(seconds)

    def _copy_content(self) -> None:
        text = self.browser.toPlainText().strip()
        if not text:
            return
        QApplication.clipboard().setText(text)
        self.status.setText("分析内容已复制")
        self.status.setStyleSheet(f"color:{theme.GREEN};")
