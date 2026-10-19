"""Settings dialog for translation engines and speech options."""

from __future__ import annotations

from typing import Any

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .config import ENGINE_LABELS, config_path
from .secrets import protect_secret, reveal_secret
from .widgets import Card


class SettingsDialog(QDialog):
    def __init__(
        self,
        settings: dict[str, Any],
        recognizers: list[dict[str, str]],
        voices: list[dict[str, Any]],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.settings = dict(settings)
        self.recognizers = recognizers
        self.voices = voices
        self.setWindowTitle("设置 · 羽中纯声")
        self.setModal(True)
        self.resize(680, 720)
        self.setMinimumSize(640, 660)
        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 22)
        root.setSpacing(14)

        title_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(3)
        title = QLabel("设置")
        title.setObjectName("PageTitle")
        subtitle = QLabel("翻译引擎、朗读和语音识别")
        subtitle.setObjectName("Muted")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        title_row.addLayout(title_box)
        title_row.addStretch()
        root.addLayout(title_row)

        engine_card = Card()
        engine_layout = QVBoxLayout(engine_card)
        engine_layout.setContentsMargins(19, 17, 19, 17)
        engine_layout.setSpacing(11)
        engine_layout.addWidget(self._section_title("翻译引擎"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(9)
        grid.addWidget(self._caption("服务"), 0, 0)
        self.engine_combo = QComboBox()
        for key in ("deepseek", "google", "mymemory", "openai"):
            self.engine_combo.addItem(ENGINE_LABELS[key], key)
        self.engine_combo.currentIndexChanged.connect(self._engine_changed)
        grid.addWidget(self.engine_combo, 0, 1)
        engine_layout.addLayout(grid)

        self.engine_hint = QLabel()
        self.engine_hint.setObjectName("Hint")
        self.engine_hint.setWordWrap(True)
        engine_layout.addWidget(self.engine_hint)

        self.deepseek_panel = QWidget()
        deepseek_grid = QGridLayout(self.deepseek_panel)
        deepseek_grid.setContentsMargins(0, 0, 0, 0)
        deepseek_grid.setHorizontalSpacing(12)
        deepseek_grid.setVerticalSpacing(9)
        self.deepseek_key = QLineEdit()
        self.deepseek_key.setEchoMode(QLineEdit.Password)
        self.deepseek_key.setPlaceholderText("sk-...")
        self.deepseek_base = QLineEdit()
        self.deepseek_model = QLineEdit()
        deepseek_grid.addWidget(self._caption("API Key"), 0, 0)
        deepseek_grid.addWidget(self.deepseek_key, 0, 1)
        deepseek_grid.addWidget(self._caption("接口地址"), 1, 0)
        deepseek_grid.addWidget(self.deepseek_base, 1, 1)
        deepseek_grid.addWidget(self._caption("模型"), 2, 0)
        deepseek_grid.addWidget(self.deepseek_model, 2, 1)
        engine_layout.addWidget(self.deepseek_panel)

        self.openai_panel = QWidget()
        openai_grid = QGridLayout(self.openai_panel)
        openai_grid.setContentsMargins(0, 0, 0, 0)
        openai_grid.setHorizontalSpacing(12)
        openai_grid.setVerticalSpacing(9)
        self.openai_key = QLineEdit()
        self.openai_key.setEchoMode(QLineEdit.Password)
        self.openai_key.setPlaceholderText("sk-...")
        self.openai_base = QLineEdit()
        self.openai_model = QLineEdit()
        openai_grid.addWidget(self._caption("API Key"), 0, 0)
        openai_grid.addWidget(self.openai_key, 0, 1)
        openai_grid.addWidget(self._caption("接口地址"), 1, 0)
        openai_grid.addWidget(self.openai_base, 1, 1)
        openai_grid.addWidget(self._caption("模型"), 2, 0)
        openai_grid.addWidget(self.openai_model, 2, 1)
        engine_layout.addWidget(self.openai_panel)

        key_note = QLabel("密钥使用 Windows 数据保护加密，仅保存在当前电脑。")
        key_note.setObjectName("Faint")
        engine_layout.addWidget(key_note)
        root.addWidget(engine_card)

        behavior_card = Card()
        behavior_layout = QVBoxLayout(behavior_card)
        behavior_layout.setContentsMargins(19, 15, 19, 15)
        behavior_layout.setSpacing(10)
        behavior_layout.addWidget(self._section_title("使用方式"))
        self.auto_translate = QCheckBox("输入停顿后自动翻译")
        self.auto_speak = QCheckBox("翻译完成后自动朗读译文")
        behavior_layout.addWidget(self.auto_translate)
        behavior_layout.addWidget(self.auto_speak)
        root.addWidget(behavior_card)

        voice_card = Card()
        voice_layout = QVBoxLayout(voice_card)
        voice_layout.setContentsMargins(19, 15, 19, 15)
        voice_layout.setSpacing(7)
        voice_layout.addWidget(self._section_title("本机语音能力"))
        recognizer_text = "、".join(
            sorted({item.get("culture", "") for item in self.recognizers if item.get("culture")})
        )
        if not recognizer_text:
            recognizer_text = "未检测到可用引擎"
        self.recognizers_label = QLabel(f"语音识别：{recognizer_text}")
        self.recognizers_label.setObjectName("Hint")
        self.recognizers_label.setWordWrap(True)
        voice_layout.addWidget(self.recognizers_label)
        voice_names = []
        for voice in self.voices:
            description = str(voice.get("description", ""))
            if description:
                voice_names.append(description.replace("Microsoft ", "").replace(" Desktop", ""))
        voice_text = "；".join(voice_names[:4]) if voice_names else "未检测到语音合成引擎"
        self.voices_label = QLabel(f"朗读语音：{voice_text}")
        self.voices_label.setObjectName("Hint")
        self.voices_label.setWordWrap(True)
        voice_layout.addWidget(self.voices_label)
        path_label = QLabel(f"配置文件：{config_path()}")
        path_label.setObjectName("Faint")
        path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        voice_layout.addWidget(path_label)
        root.addWidget(voice_card)

        root.addStretch()
        footer = QHBoxLayout()
        footer.addStretch()
        cancel = QPushButton("取消")
        cancel.setObjectName("SecondaryButton")
        cancel.clicked.connect(self.reject)
        save = QPushButton("保存设置")
        save.setObjectName("PrimaryButton")
        save.setMinimumWidth(132)
        save.clicked.connect(self._save)
        footer.addWidget(cancel)
        footer.addWidget(save)
        root.addLayout(footer)

    def _section_title(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("CardTitle")
        return label

    def _caption(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("Muted")
        label.setMinimumWidth(72)
        return label

    def _load_values(self) -> None:
        engine = str(self.settings.get("engine", "deepseek"))
        index = self.engine_combo.findData(engine)
        self.engine_combo.setCurrentIndex(max(0, index))
        self.deepseek_key.setText(reveal_secret(str(self.settings.get("deepseek_api_key", ""))))
        self.deepseek_base.setText(
            str(self.settings.get("deepseek_base_url", "https://api.deepseek.com"))
        )
        self.deepseek_model.setText(str(self.settings.get("deepseek_model", "deepseek-chat")))
        self.openai_key.setText(reveal_secret(str(self.settings.get("openai_api_key", ""))))
        self.openai_base.setText(str(self.settings.get("openai_base_url", "https://api.openai.com/v1")))
        self.openai_model.setText(str(self.settings.get("openai_model", "gpt-4o-mini")))
        self.auto_translate.setChecked(bool(self.settings.get("auto_translate", False)))
        self.auto_speak.setChecked(bool(self.settings.get("auto_speak", True)))
        self._engine_changed()

    def _engine_changed(self) -> None:
        engine = str(self.engine_combo.currentData())
        self.deepseek_panel.setVisible(engine == "deepseek")
        self.openai_panel.setVisible(engine == "openai")
        hints = {
            "deepseek": "DeepSeek 擅长中英互译，速度快，适合日常使用。",
            "google": "无需密钥，使用 Google 免费翻译接口，可能受网络环境影响。",
            "mymemory": "无需密钥，单次最多 500 个字符，适合短句。",
            "openai": "可连接 OpenAI 或任意兼容 /chat/completions 的服务。",
        }
        self.engine_hint.setText(hints.get(engine, ""))

    def _save(self) -> None:
        engine = str(self.engine_combo.currentData())
        if engine == "deepseek" and not self.deepseek_key.text().strip():
            QMessageBox.warning(self, "缺少密钥", "使用 DeepSeek 翻译前，请填写 API Key。")
            return
        self.settings.update(
            {
                "engine": engine,
                "deepseek_api_key": protect_secret(self.deepseek_key.text()),
                "deepseek_base_url": self.deepseek_base.text().strip()
                or "https://api.deepseek.com",
                "deepseek_model": self.deepseek_model.text().strip() or "deepseek-chat",
                "openai_api_key": protect_secret(self.openai_key.text()),
                "openai_base_url": self.openai_base.text().strip(),
                "openai_model": self.openai_model.text().strip(),
                "auto_translate": self.auto_translate.isChecked(),
                "auto_speak": self.auto_speak.isChecked(),
            }
        )
        self.accept()

