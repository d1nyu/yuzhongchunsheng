"""Main application window and interaction flow."""

from __future__ import annotations

import re
import importlib.util
from difflib import SequenceMatcher
from typing import Any

from PyQt5.QtCore import QByteArray, QRect, QTimer, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QKeySequence, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QShortcut,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .audio_translate import SystemAudioTranscriber, whisper_is_available
from .config import ENGINE_LABELS, load_settings, save_settings
from .hotkeys import GlobalHotkeyFilter
from .languages import (
    SOURCE_LANGUAGES,
    TARGET_LANGUAGES,
    app_language_from_asr,
    detect_language_heuristic,
    language_for_culture,
    language_label,
    sapi_lcid,
    speech_culture_for_source,
)
from .ocr import SubtitleOcrWorker
from .overlay import QuickTranslationPopup, RegionSelector, SubtitleOverlay
from .secrets import reveal_secret
from .settings_dialog import SettingsDialog
from .speech import (
    RecognitionWorker,
    WindowsSpeaker,
    list_installed_recognizers,
    list_sapi_voices,
)
from .translation import TranslationResult, TranslationService
from .widgets import (
    Card,
    LineIconButton,
    LogoMark,
    MicButton,
    SegmentedControl,
    Toast,
    WaveformWidget,
    add_shadow,
)


class TranslateWorker(QThread):
    result_ready = pyqtSignal(int, str, object)
    error_ready = pyqtSignal(int, str, str)

    def __init__(
        self,
        request_id: int,
        context: str,
        settings: dict[str, Any],
        text: str,
        source: str,
        target: str,
        translation_context: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.request_id = request_id
        self.context = context
        self.settings = dict(settings)
        self.text = text
        self.source = source
        self.target = target
        self.translation_context = translation_context

    def run(self) -> None:
        try:
            service = TranslationService(self.settings)
            result = service.translate(
                self.text,
                self.source,
                self.target,
                context=self.translation_context,
                style="spoken" if self.context in {"video", "voice"} else "natural",
            )
            self.result_ready.emit(self.request_id, self.context, result)
        except Exception as exc:
            self.error_ready.emit(self.request_id, self.context, str(exc))


class MainWindow(QMainWindow):
    MAX_CHARS = 5000

    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.installed_recognizers = list_installed_recognizers()
        self.installed_voices = list_sapi_voices()
        self.installed_voice_languages = {
            int(item.get("language", 0)) for item in self.installed_voices
        }
        self.recognizer_cultures = [
            item.get("culture", "")
            for item in self.installed_recognizers
            if item.get("culture")
        ]
        self.speaker = WindowsSpeaker(self)
        self.speaker.error.connect(self._on_speaker_error)

        self._mode = 0
        self._request_seq = 0
        self._translating = False
        self._workers: set[TranslateWorker] = set()
        self._speech_worker: RecognitionWorker | None = None
        self._speech_source_culture: str | None = None
        self._last_text_translated = ""
        self._settings_open = False
        self._video_region: QRect | None = None
        self._video_monitoring = False
        self._ocr_worker: SubtitleOcrWorker | None = None
        self._retired_ocr_workers: set[SubtitleOcrWorker] = set()
        self._region_selector: RegionSelector | None = None
        self._overlay: SubtitleOverlay | None = None
        self._last_video_ocr_key = ""
        self._last_video_translated_source = ""
        self._video_history: list[str] = []
        self._audio_detected_language = ""
        self._audio_transcriber: SystemAudioTranscriber | None = None
        self._text_ocr_worker: SubtitleOcrWorker | None = None
        self._text_ocr_pending = False
        self._text_region_selector: RegionSelector | None = None
        self._quick_popup: QuickTranslationPopup | None = None
        self._quick_region: QRect | None = None
        self._quick_source_text = ""
        self._quick_seq = 0
        self._hotkey_filter: GlobalHotkeyFilter | None = None

        self.setWindowTitle("羽中纯声 · 文字 / 语音 / 视频翻译")
        self.setMinimumSize(1020, 720)
        self.resize(1180, 820)
        self.auto_timer = QTimer(self)
        self.auto_timer.setSingleShot(True)
        self.auto_timer.setInterval(760)
        self.auto_timer.timeout.connect(self._auto_translate)
        self.video_capture_timer = QTimer(self)
        self.video_capture_timer.setInterval(900)
        self.video_capture_timer.timeout.connect(self._video_capture_tick)
        self.video_debounce_timer = QTimer(self)
        self.video_debounce_timer.setSingleShot(True)
        self.video_debounce_timer.setInterval(280)
        self.video_debounce_timer.timeout.connect(self._translate_video_subtitle)
        self._build_ui()
        self._bind_shortcuts()
        self._restore_state()
        self._setup_global_hotkey()

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("Window")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(30, 19, 30, 16)
        root.setSpacing(12)

        root.addLayout(self._build_header())
        root.addLayout(self._build_mode_row())
        root.addWidget(self._build_language_card())

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_text_page())
        self.stack.addWidget(self._build_voice_page())
        self.stack.addWidget(self._build_video_page())
        root.addWidget(self.stack, 1)

        self.toast = Toast(central)

    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(LogoMark())
        titles = QVBoxLayout()
        titles.setSpacing(0)
        name = QLabel("羽中纯声")
        name.setObjectName("AppName")
        tagline = QLabel("羽落成声 · 文字 · 语音 · 视频翻译")
        tagline.setObjectName("AppTagline")
        titles.addWidget(name)
        titles.addWidget(tagline)
        row.addLayout(titles)
        row.addStretch()

        self.engine_badge = QLabel("DeepSeek")
        self.engine_badge.setObjectName("EnginePill")
        row.addWidget(self.engine_badge)

        self.settings_button = LineIconButton("settings", "设置", self, 42)
        self.settings_button.setObjectName("SettingsButton")
        self.settings_button.clicked.connect(self._open_settings)
        row.addWidget(self.settings_button)
        return row

    def _build_mode_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)
        self.mode_control = SegmentedControl(["文字翻译", "语音翻译", "视频翻译"])
        self.mode_control.currentChanged.connect(self._mode_changed)
        row.addWidget(self.mode_control)
        row.addStretch()
        self.auto_translate_check = QCheckBox("自动翻译")
        self.auto_translate_check.setToolTip("在文字输入停顿后自动翻译")
        self.auto_translate_check.toggled.connect(self._behavior_changed)
        self.auto_speak_check = QCheckBox("自动朗读")
        self.auto_speak_check.setToolTip("翻译完成后自动朗读译文")
        self.auto_speak_check.toggled.connect(self._behavior_changed)
        row.addWidget(self.auto_translate_check)
        row.addWidget(self.auto_speak_check)
        return row

    def _build_language_card(self) -> Card:
        card = Card()
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(9)

        source_caption = QLabel("从")
        source_caption.setObjectName("Muted")
        layout.addWidget(source_caption)
        self.source_combo = QComboBox()
        self.source_combo.setMinimumWidth(186)
        for language in SOURCE_LANGUAGES:
            self.source_combo.addItem(language.label, language.code)
        layout.addWidget(self.source_combo)

        self.swap_button = LineIconButton("swap", "交换语言", self, 34)
        self.swap_button.setObjectName("SwapButton")
        self.swap_button.clicked.connect(self._swap_languages)
        layout.addWidget(self.swap_button)

        target_caption = QLabel("到")
        target_caption.setObjectName("Muted")
        layout.addWidget(target_caption)
        self.target_combo = QComboBox()
        self.target_combo.setMinimumWidth(186)
        for language in TARGET_LANGUAGES:
            self.target_combo.addItem(language.label, language.code)
        layout.addWidget(self.target_combo)
        layout.addStretch()

        shortcut_hint = QLabel("Ctrl + Enter  翻译")
        shortcut_hint.setObjectName("Faint")
        layout.addWidget(shortcut_hint)
        return card

    def _build_text_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        cards = QHBoxLayout()
        cards.setSpacing(14)

        source_card = Card()
        source_card.setMinimumHeight(322)
        source_layout = QVBoxLayout(source_card)
        source_layout.setContentsMargins(18, 15, 18, 12)
        source_layout.setSpacing(9)
        source_header = QHBoxLayout()
        source_title = QLabel("原文")
        source_title.setObjectName("CardTitle")
        source_header.addWidget(source_title)
        self.text_source_badge = QLabel("自动检测")
        self.text_source_badge.setObjectName("Badge")
        source_header.addWidget(self.text_source_badge)
        source_header.addStretch()
        self.char_count = QLabel(f"0 / {self.MAX_CHARS}")
        self.char_count.setObjectName("Faint")
        source_header.addWidget(self.char_count)
        source_layout.addLayout(source_header)
        source_layout.addWidget(self._separator())

        self.source_edit = QTextEdit()
        self.source_edit.setObjectName("SourceEdit")
        self.source_edit.setAcceptRichText(False)
        self.source_edit.setPlaceholderText("输入或粘贴要翻译的内容…")
        self.source_edit.textChanged.connect(self._source_text_changed)
        source_layout.addWidget(self.source_edit, 1)

        source_footer = QHBoxLayout()
        source_footer.setSpacing(2)
        self.clear_button = LineIconButton("clear", "清空", self)
        self.clear_button.clicked.connect(self._clear_text)
        source_footer.addWidget(self.clear_button)
        self.paste_button = LineIconButton("paste", "粘贴", self)
        self.paste_button.clicked.connect(self._paste_text)
        source_footer.addWidget(self.paste_button)
        self.screen_pick_button = QPushButton("选区翻译  Ctrl+Alt+T")
        self.screen_pick_button.setObjectName("GhostButton")
        self.screen_pick_button.setToolTip("框选屏幕上的文字并自动识别翻译")
        self.screen_pick_button.clicked.connect(self._start_text_selection)
        source_footer.addWidget(self.screen_pick_button)
        source_footer.addStretch()
        self.source_speak_button = LineIconButton("speaker", "朗读原文", self)
        self.source_speak_button.clicked.connect(self._speak_source)
        source_footer.addWidget(self.source_speak_button)
        source_layout.addLayout(source_footer)
        cards.addWidget(source_card, 1)

        result_card = Card(result=True)
        result_card.setMinimumHeight(322)
        result_layout = QVBoxLayout(result_card)
        result_layout.setContentsMargins(18, 15, 18, 12)
        result_layout.setSpacing(9)
        result_header = QHBoxLayout()
        result_title = QLabel("译文")
        result_title.setObjectName("CardTitle")
        result_header.addWidget(result_title)
        self.text_target_badge = QLabel("英语")
        self.text_target_badge.setObjectName("Badge")
        result_header.addWidget(self.text_target_badge)
        result_header.addStretch()
        self.text_provider_badge = QLabel("DeepSeek")
        self.text_provider_badge.setObjectName("ProviderBadge")
        self.text_provider_badge.setVisible(False)
        result_header.addWidget(self.text_provider_badge)
        result_layout.addLayout(result_header)
        result_layout.addWidget(self._separator())

        self.text_result_edit = QTextEdit()
        self.text_result_edit.setObjectName("ResultEdit")
        self.text_result_edit.setReadOnly(True)
        self.text_result_edit.setAcceptRichText(False)
        self.text_result_edit.setPlaceholderText("译文会显示在这里")
        result_layout.addWidget(self.text_result_edit, 1)

        result_footer = QHBoxLayout()
        result_footer.setSpacing(2)
        result_note = QLabel("译文仅供参考")
        result_note.setObjectName("Faint")
        result_footer.addWidget(result_note)
        result_footer.addStretch()
        self.result_speak_button = LineIconButton("speaker", "朗读译文", self)
        self.result_speak_button.clicked.connect(self._speak_result)
        result_footer.addWidget(self.result_speak_button)
        self.copy_button = LineIconButton("copy", "复制译文", self)
        self.copy_button.clicked.connect(self._copy_result)
        result_footer.addWidget(self.copy_button)
        result_layout.addLayout(result_footer)
        cards.addWidget(result_card, 1)
        layout.addLayout(cards, 1)

        action_row = QHBoxLayout()
        self.text_status_dot = QFrame()
        self.text_status_dot.setFixedSize(8, 8)
        self.text_status_dot.setStyleSheet(
            f"background:{theme.GREEN};border-radius:4px;"
        )
        self.text_status = QLabel("文字翻译已就绪")
        self.text_status.setObjectName("Muted")
        action_row.addWidget(self.text_status_dot)
        action_row.addWidget(self.text_status)
        action_row.addStretch()
        self.translate_button = QPushButton("翻译")
        self.translate_button.setObjectName("PrimaryButton")
        self.translate_button.setMinimumWidth(164)
        self.translate_button.clicked.connect(lambda: self._translate_current(True))
        action_row.addWidget(self.translate_button)
        layout.addLayout(action_row)
        return page

    def _build_voice_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        stage = QFrame()
        stage.setObjectName("VoiceStage")
        stage.setMinimumHeight(238)
        add_shadow(stage, 28, 7, 18)
        stage_layout = QVBoxLayout(stage)
        stage_layout.setContentsMargins(22, 13, 22, 10)
        stage_layout.setSpacing(2)
        self.voice_headline = QLabel("点击话筒，开始说话")
        self.voice_headline.setAlignment(Qt.AlignCenter)
        self.voice_headline.setStyleSheet(
            "font-size:19px;font-weight:600;color:#3A2226;"
        )
        stage_layout.addWidget(self.voice_headline)
        self.voice_hint = QLabel("说完停顿一下，识别会自动结束")
        self.voice_hint.setObjectName("Muted")
        self.voice_hint.setAlignment(Qt.AlignCenter)
        stage_layout.addWidget(self.voice_hint)

        mic_row = QHBoxLayout()
        mic_row.addStretch()
        self.mic_button = MicButton()
        self.mic_button.clicked.connect(self._toggle_listening)
        mic_row.addWidget(self.mic_button)
        mic_row.addStretch()
        stage_layout.addLayout(mic_row)

        self.waveform = WaveformWidget()
        self.waveform.setMaximumWidth(520)
        wave_row = QHBoxLayout()
        wave_row.addStretch()
        wave_row.addWidget(self.waveform)
        wave_row.addStretch()
        stage_layout.addLayout(wave_row)

        engine_row = QHBoxLayout()
        engine_row.addStretch()
        self.speech_engine_pill = QLabel("本机语音识别")
        self.speech_engine_pill.setObjectName("SpeechEnginePill")
        engine_row.addWidget(self.speech_engine_pill)
        engine_row.addStretch()
        stage_layout.addLayout(engine_row)
        layout.addWidget(stage)

        cards = QHBoxLayout()
        cards.setSpacing(14)
        source_card = Card()
        source_card.setMinimumHeight(230)
        source_layout = QVBoxLayout(source_card)
        source_layout.setContentsMargins(17, 14, 17, 11)
        source_layout.setSpacing(8)
        source_header = QHBoxLayout()
        source_title = QLabel("识别结果")
        source_title.setObjectName("CardTitle")
        source_header.addWidget(source_title)
        self.voice_source_badge = QLabel("语音")
        self.voice_source_badge.setObjectName("Badge")
        source_header.addWidget(self.voice_source_badge)
        source_header.addStretch()
        source_layout.addLayout(source_header)
        source_layout.addWidget(self._separator())
        self.voice_source_edit = QTextEdit()
        self.voice_source_edit.setObjectName("VoiceSourceEdit")
        self.voice_source_edit.setAcceptRichText(False)
        self.voice_source_edit.setPlaceholderText("说话后，识别出的文字会显示在这里")
        self.voice_source_edit.textChanged.connect(self._voice_text_changed)
        source_layout.addWidget(self.voice_source_edit, 1)
        cards.addWidget(source_card, 1)

        result_card = Card(result=True)
        result_card.setMinimumHeight(230)
        result_layout = QVBoxLayout(result_card)
        result_layout.setContentsMargins(17, 14, 17, 11)
        result_layout.setSpacing(8)
        result_header = QHBoxLayout()
        result_title = QLabel("译文")
        result_title.setObjectName("CardTitle")
        result_header.addWidget(result_title)
        self.voice_target_badge = QLabel("英语")
        self.voice_target_badge.setObjectName("Badge")
        result_header.addWidget(self.voice_target_badge)
        result_header.addStretch()
        self.voice_provider_badge = QLabel("DeepSeek")
        self.voice_provider_badge.setObjectName("ProviderBadge")
        self.voice_provider_badge.setVisible(False)
        result_header.addWidget(self.voice_provider_badge)
        result_layout.addLayout(result_header)
        result_layout.addWidget(self._separator())
        self.voice_result_edit = QTextEdit()
        self.voice_result_edit.setObjectName("VoiceResultEdit")
        self.voice_result_edit.setReadOnly(True)
        self.voice_result_edit.setAcceptRichText(False)
        self.voice_result_edit.setPlaceholderText("语音翻译结果会显示在这里")
        result_layout.addWidget(self.voice_result_edit, 1)
        voice_result_footer = QHBoxLayout()
        voice_result_footer.setSpacing(2)
        voice_result_footer.addStretch()
        self.voice_speak_button = LineIconButton("speaker", "朗读译文", self)
        self.voice_speak_button.clicked.connect(self._speak_voice_result)
        voice_result_footer.addWidget(self.voice_speak_button)
        self.voice_copy_button = LineIconButton("copy", "复制译文", self)
        self.voice_copy_button.clicked.connect(self._copy_voice_result)
        voice_result_footer.addWidget(self.voice_copy_button)
        result_layout.addLayout(voice_result_footer)
        cards.addWidget(result_card, 1)
        layout.addLayout(cards, 1)

        action_row = QHBoxLayout()
        self.voice_status_dot = QFrame()
        self.voice_status_dot.setFixedSize(8, 8)
        self.voice_status_dot.setStyleSheet(
            f"background:{theme.GREEN};border-radius:4px;"
        )
        self.voice_status = QLabel("点击话筒开始语音翻译")
        self.voice_status.setObjectName("Muted")
        action_row.addWidget(self.voice_status_dot)
        action_row.addWidget(self.voice_status)
        action_row.addStretch()
        self.voice_stop_button = QPushButton("停止聆听")
        self.voice_stop_button.setObjectName("SecondaryButton")
        self.voice_stop_button.setVisible(False)
        self.voice_stop_button.clicked.connect(self._stop_listening)
        action_row.addWidget(self.voice_stop_button)
        self.voice_translate_button = QPushButton("重新翻译")
        self.voice_translate_button.setObjectName("SecondaryButton")
        self.voice_translate_button.setEnabled(False)
        self.voice_translate_button.clicked.connect(lambda: self._translate_current(True))
        action_row.addWidget(self.voice_translate_button)
        layout.addLayout(action_row)
        return page

    def _build_video_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        stage = Card()
        stage.setMinimumHeight(190)
        stage_layout = QHBoxLayout(stage)
        stage_layout.setContentsMargins(22, 17, 18, 17)
        stage_layout.setSpacing(22)

        info_column = QVBoxLayout()
        info_column.setSpacing(5)
        self.video_headline = QLabel("框选字幕区域，实时看懂视频")
        self.video_headline.setStyleSheet(
            "font-size:20px;font-weight:600;color:#3A2226;"
        )
        info_column.addWidget(self.video_headline)
        self.video_hint = QLabel(
            "框选画面中的字幕条，程序会持续识别新增字幕并自动翻译。"
        )
        self.video_hint.setObjectName("Muted")
        self.video_hint.setWordWrap(True)
        info_column.addWidget(self.video_hint)

        source_row = QHBoxLayout()
        source_row.setSpacing(8)
        source_caption = QLabel("识别来源")
        source_caption.setObjectName("Muted")
        source_row.addWidget(source_caption)
        self.video_source_combo = QComboBox()
        self.video_source_combo.addItem("画面字幕", "subtitle")
        self.video_source_combo.addItem("电脑声音（无需字幕）", "audio")
        self.video_source_combo.setMinimumWidth(176)
        self.video_source_combo.currentIndexChanged.connect(self._video_source_changed)
        source_row.addWidget(self.video_source_combo)
        source_row.addStretch()
        info_column.addLayout(source_row)

        self.video_region_label = QLabel("尚未选择字幕区域")
        self.video_region_label.setObjectName("Faint")
        info_column.addWidget(self.video_region_label)
        info_column.addStretch()

        button_row = QHBoxLayout()
        button_row.setSpacing(9)
        self.video_select_button = QPushButton("框选字幕区域")
        self.video_select_button.setObjectName("SecondaryButton")
        self.video_select_button.clicked.connect(self._select_video_region)
        button_row.addWidget(self.video_select_button)
        self.video_start_button = QPushButton("开始识别")
        self.video_start_button.setObjectName("PrimaryButton")
        self.video_start_button.setMinimumWidth(138)
        self.video_start_button.setEnabled(False)
        self.video_start_button.clicked.connect(self._toggle_video_monitoring)
        button_row.addWidget(self.video_start_button)
        info_column.addLayout(button_row)

        video_options = QHBoxLayout()
        self.video_overlay_check = QCheckBox("显示置顶悬浮字幕")
        self.video_overlay_check.setChecked(True)
        self.video_overlay_check.toggled.connect(self._video_overlay_toggled)
        video_options.addWidget(self.video_overlay_check)
        self.video_engine_pill = QLabel("Vosk · 本地 · 英语")
        self.video_engine_pill.setObjectName("SpeechEnginePill")
        video_options.addWidget(self.video_engine_pill)
        video_options.addStretch()
        info_column.addLayout(video_options)
        stage_layout.addLayout(info_column, 1)

        self.video_preview = QLabel("尚未选择区域")
        self.video_preview.setAlignment(Qt.AlignCenter)
        self.video_preview.setFixedSize(326, 150)
        self.video_preview.setStyleSheet(
            "background:#111827;color:#8190A6;border:1px solid #253148;"
            "border-radius:12px;font-size:11px;"
        )
        stage_layout.addWidget(self.video_preview, 0, Qt.AlignVCenter)
        layout.addWidget(stage)

        cards = QHBoxLayout()
        cards.setSpacing(14)
        source_card = Card()
        source_card.setMinimumHeight(230)
        source_layout = QVBoxLayout(source_card)
        source_layout.setContentsMargins(17, 14, 17, 11)
        source_layout.setSpacing(8)
        source_header = QHBoxLayout()
        source_title = QLabel("识别内容")
        source_title.setObjectName("CardTitle")
        source_header.addWidget(source_title)
        self.video_source_badge = QLabel("本地 OCR")
        self.video_source_badge.setObjectName("Badge")
        source_header.addWidget(self.video_source_badge)
        source_header.addStretch()
        source_layout.addLayout(source_header)
        source_layout.addWidget(self._separator())
        self.video_source_edit = QTextEdit()
        self.video_source_edit.setObjectName("VoiceSourceEdit")
        self.video_source_edit.setAcceptRichText(False)
        self.video_source_edit.setPlaceholderText("框选字幕区域后，识别出的字幕会显示在这里")
        self.video_source_edit.textChanged.connect(self._video_text_changed)
        source_layout.addWidget(self.video_source_edit, 1)
        cards.addWidget(source_card, 1)

        result_card = Card(result=True)
        result_card.setMinimumHeight(230)
        result_layout = QVBoxLayout(result_card)
        result_layout.setContentsMargins(17, 14, 17, 11)
        result_layout.setSpacing(8)
        result_header = QHBoxLayout()
        result_title = QLabel("译文")
        result_title.setObjectName("CardTitle")
        result_header.addWidget(result_title)
        self.video_target_badge = QLabel("中文（简体）")
        self.video_target_badge.setObjectName("Badge")
        result_header.addWidget(self.video_target_badge)
        result_header.addStretch()
        self.video_provider_badge = QLabel("DeepSeek")
        self.video_provider_badge.setObjectName("ProviderBadge")
        self.video_provider_badge.setVisible(False)
        result_header.addWidget(self.video_provider_badge)
        result_layout.addLayout(result_header)
        result_layout.addWidget(self._separator())
        self.video_result_edit = QTextEdit()
        self.video_result_edit.setObjectName("VoiceResultEdit")
        self.video_result_edit.setReadOnly(True)
        self.video_result_edit.setAcceptRichText(False)
        self.video_result_edit.setPlaceholderText("字幕译文会显示在这里")
        result_layout.addWidget(self.video_result_edit, 1)
        video_result_footer = QHBoxLayout()
        video_result_footer.setSpacing(2)
        video_result_footer.addStretch()
        self.video_speak_button = LineIconButton("speaker", "朗读当前译文", self)
        self.video_speak_button.clicked.connect(self._speak_video_result)
        video_result_footer.addWidget(self.video_speak_button)
        self.video_copy_button = LineIconButton("copy", "复制当前译文", self)
        self.video_copy_button.clicked.connect(self._copy_video_result)
        video_result_footer.addWidget(self.video_copy_button)
        result_layout.addLayout(video_result_footer)
        cards.addWidget(result_card, 1)
        layout.addLayout(cards, 1)

        action_row = QHBoxLayout()
        self.video_status_dot = QFrame()
        self.video_status_dot.setFixedSize(8, 8)
        self.video_status_dot.setStyleSheet(
            f"background:{theme.FAINT};border-radius:4px;"
        )
        self.video_status = QLabel("先框选视频里的字幕区域")
        self.video_status.setObjectName("Muted")
        action_row.addWidget(self.video_status_dot)
        action_row.addWidget(self.video_status)
        action_row.addStretch()
        self.video_translate_button = QPushButton("重新翻译")
        self.video_translate_button.setObjectName("SecondaryButton")
        self.video_translate_button.setEnabled(False)
        self.video_translate_button.clicked.connect(lambda: self._translate_current(True))
        action_row.addWidget(self.video_translate_button)
        layout.addLayout(action_row)
        return page

    @staticmethod
    def _separator() -> QFrame:
        line = QFrame()
        line.setObjectName("Separator")
        line.setFrameShape(QFrame.NoFrame)
        return line

    def _bind_shortcuts(self) -> None:
        shortcuts = (
            ("Ctrl+Return", lambda: self._translate_current(True)),
            ("Ctrl+Enter", lambda: self._translate_current(True)),
            ("Ctrl+Alt+T", self._start_text_selection),
            ("Ctrl+Shift+C", self._copy_current),
            ("Ctrl+Shift+S", self._speak_current_result),
            ("Ctrl+L", self._focus_source),
            ("Escape", self._escape),
        )
        self._shortcuts = []
        for sequence, callback in shortcuts:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.WindowShortcut)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)

    def _setup_global_hotkey(self) -> None:
        hotkey = GlobalHotkeyFilter(parent=self)
        hotkey.triggered.connect(self._start_text_selection)
        if hotkey.register():
            self._hotkey_filter = hotkey
        else:
            self.toast.show_message(
                "全局快捷键 Ctrl+Alt+T 被其他程序占用，程序内快捷键仍可使用。",
                "info",
                4200,
            )

    def _restore_state(self) -> None:
        geometry = str(self.settings.get("geometry", ""))
        if geometry:
            try:
                self.restoreGeometry(QByteArray.fromBase64(geometry.encode("ascii")))
            except (ValueError, TypeError):
                pass

        source = str(self.settings.get("source_lang", "auto"))
        target = str(self.settings.get("target_lang", "en"))
        source_index = self.source_combo.findData(source)
        target_index = self.target_combo.findData(target)
        self.source_combo.setCurrentIndex(max(0, source_index))
        self.target_combo.setCurrentIndex(max(0, target_index))

        self.auto_translate_check.blockSignals(True)
        self.auto_speak_check.blockSignals(True)
        self.auto_translate_check.setChecked(bool(self.settings.get("auto_translate", False)))
        self.auto_speak_check.setChecked(bool(self.settings.get("auto_speak", True)))
        self.auto_translate_check.blockSignals(False)
        self.auto_speak_check.blockSignals(False)

        self.source_combo.currentIndexChanged.connect(self._language_changed)
        self.target_combo.currentIndexChanged.connect(self._language_changed)
        self._language_changed()
        self._update_engine_badge()
        self._update_speech_engine_hint()
        self._restore_video_settings()

        last_mode = str(self.settings.get("last_mode", "text"))
        mode = {"voice": 1, "video": 2}.get(last_mode, 0)
        if mode:
            self.mode_control.setCurrentIndex(mode)
            self.stack.setCurrentIndex(mode)
            self._mode = mode
        self._mode_changed(mode)

    def _source_code(self) -> str:
        return str(self.source_combo.currentData() or "auto")

    def _target_code(self) -> str:
        return str(self.target_combo.currentData() or "en")

    def _mode_changed(self, index: int) -> None:
        index = index if index in (0, 1, 2) else 0
        if index != 2 and self._video_monitoring:
            self._stop_video_monitoring()
        if self._speech_worker is not None and self._speech_worker.isRunning() and index == 0:
            self._stop_listening()
        self._mode = index
        self.stack.setCurrentIndex(index)
        self.settings["last_mode"] = ("text", "voice", "video")[index]
        self.auto_translate_check.setEnabled(index == 0)
        self.auto_speak_check.setEnabled(index != 2)
        self.auto_translate_check.setToolTip(
            "在文字输入停顿后自动翻译" if index == 0 else "语音模式下会自动翻译识别结果"
        )
        self.auto_speak_check.setToolTip(
            "视频字幕模式只显示文字，不自动朗读"
            if index == 2
            else "翻译完成后自动朗读译文"
        )
        if index == 0:
            self._set_text_status("ready", "文字翻译已就绪")
            self.translate_button.setEnabled(
                bool(self.source_edit.toPlainText().strip()) and not self._translating
            )
            self.auto_translate_check.setToolTip("在文字输入停顿后自动翻译")
        elif index == 1:
            self._set_voice_status("ready", "点击话筒开始语音翻译")
            self.voice_translate_button.setEnabled(
                bool(self.voice_source_edit.toPlainText().strip())
            )
            self.auto_translate_check.setToolTip("语音模式下会自动翻译识别结果")
        else:
            if self._video_source_mode() == "audio":
                self._set_video_status(
                    "ready",
                    "正在监听电脑声音"
                    if self._video_monitoring
                    else "点击“开始识别”监听视频声音",
                )
            else:
                self._set_video_status(
                    "ready",
                    "正在监听字幕"
                    if self._video_monitoring
                    else "先框选视频里的字幕区域",
                )
            self.video_translate_button.setEnabled(
                bool(self.video_source_edit.toPlainText().strip())
            )
            self.auto_translate_check.setToolTip("视频字幕模式会自动翻译新增字幕")
        self._save_settings_quietly()

    def _language_changed(self) -> None:
        source = self._source_code()
        target = self._target_code()
        self._speech_source_culture = None
        source_text = (
            "自动检测"
            if source == "auto"
            else language_label(source)
        )
        self.text_source_badge.setText(source_text)
        self.voice_source_badge.setText(
            "语音 · 自动" if source == "auto" else f"语音 · {language_label(source)}"
        )
        self.text_target_badge.setText(language_label(target))
        self.voice_target_badge.setText(language_label(target))
        self.video_target_badge.setText(language_label(target))
        self.settings["source_lang"] = source
        self.settings["target_lang"] = target
        self._save_settings_quietly()
        if self.auto_translate_check.isChecked() and self._mode == 0:
            text = self.source_edit.toPlainText().strip()
            if text and text != self._last_text_translated:
                self.auto_timer.start()

    def _behavior_changed(self) -> None:
        self.settings["auto_translate"] = self.auto_translate_check.isChecked()
        self.settings["auto_speak"] = self.auto_speak_check.isChecked()
        self._save_settings_quietly()
        if self.auto_translate_check.isChecked() and self._mode == 0:
            text = self.source_edit.toPlainText().strip()
            if text:
                self.auto_timer.start()

    def _update_engine_badge(self) -> None:
        engine = str(self.settings.get("engine", "deepseek"))
        label = ENGINE_LABELS.get(engine, "翻译引擎")
        if engine == "deepseek" and not reveal_secret(
            str(self.settings.get("deepseek_api_key", ""))
        ):
            label += " · 未配置"
        elif engine == "openai" and not reveal_secret(
            str(self.settings.get("openai_api_key", ""))
        ):
            label += " · 未配置"
        self.engine_badge.setText(label)

    def _update_speech_engine_hint(self) -> None:
        labels: list[str] = []
        for culture in self.recognizer_cultures:
            language = language_for_culture(culture)
            text = language.label if language else culture
            if text not in labels:
                labels.append(text)
        if labels:
            display = "、".join(labels[:3])
            if len(labels) > 3:
                display += f" 等 {len(labels)} 种"
            self.speech_engine_pill.setText(f"本机识别 · {display}")
            self.mic_button.setEnabled(True)
        else:
            self.speech_engine_pill.setText("未检测到语音识别引擎")
            self.mic_button.setEnabled(False)
            self.voice_hint.setText(
                "请在 Windows“时间和语言 → 语音”中安装语音识别包"
            )

    def _restore_video_settings(self) -> None:
        source_mode = str(self.settings.get("audio_source_mode", "audio"))
        source_index = self.video_source_combo.findData(source_mode)
        self.video_source_combo.blockSignals(True)
        self.video_source_combo.setCurrentIndex(max(0, source_index))
        self.video_source_combo.blockSignals(False)

        raw_region = self.settings.get("video_region", [])
        if isinstance(raw_region, list) and len(raw_region) == 4:
            try:
                region = QRect(*(int(value) for value in raw_region))
            except (TypeError, ValueError):
                region = QRect()
            if region.width() >= 80 and region.height() >= 22:
                self._video_region = region
                self._update_video_region_ui()

        self.video_overlay_check.blockSignals(True)
        self.video_overlay_check.setChecked(
            bool(self.settings.get("overlay_enabled", True))
        )
        self.video_overlay_check.blockSignals(False)
        self._update_video_mode_ui()

    def _video_source_mode(self) -> str:
        return str(self.video_source_combo.currentData() or "audio")

    def _video_source_changed(self) -> None:
        mode = self._video_source_mode()
        if self._video_monitoring:
            self._stop_video_monitoring()
        self.settings["audio_source_mode"] = mode
        self._save_settings_quietly()
        self._update_video_mode_ui()

    def _update_video_mode_ui(self) -> None:
        mode = self._video_source_mode()
        if mode == "audio":
            self.video_headline.setText("用电脑声音实时翻译视频")
            self.video_hint.setText(
                "无需字幕。Whisper 自动识别语言，并按说话停顿断句后交给 DeepSeek 翻译。"
            )
            self.video_region_label.setText(
                "声音来源：默认扬声器回环 · 不占用麦克风"
            )
            self.video_select_button.setVisible(False)
            self.video_start_button.setEnabled(True)
            self.video_preview.setPixmap(QPixmap())
            self.video_preview.setText(
                "电脑声音\n\nWhisper 多语言转写\nDeepSeek 翻译"
            )
            engine = "Whisper · 本地 · 多语言" if whisper_is_available() else "Vosk · 本地 · 英语"
            self.video_engine_pill.setText(engine)
            self.video_source_badge.setText("Whisper 语音" if whisper_is_available() else "Vosk 语音")
            self.video_source_edit.setPlaceholderText(
                "电脑播放的语音会在这里自动转写为文字"
            )
            self.video_result_edit.setPlaceholderText("翻译结果会显示在这里")
            self._set_video_status("ready", "点击“开始识别”监听视频声音")
        else:
            self.video_headline.setText("框选字幕区域，实时看懂视频")
            self.video_hint.setText(
                "框选画面中的字幕条，程序会持续识别新增字幕并自动翻译。"
            )
            self.video_select_button.setVisible(True)
            self.video_engine_pill.setText("本地 OCR · 中英文")
            self.video_source_badge.setText("本地 OCR")
            self.video_source_edit.setPlaceholderText(
                "框选字幕区域后，识别出的字幕会显示在这里"
            )
            self.video_result_edit.setPlaceholderText("字幕译文会显示在这里")
            self._update_video_region_ui()
            if self._video_region is not None:
                QTimer.singleShot(120, self._refresh_video_preview)
            else:
                self.video_preview.setPixmap(QPixmap())
                self.video_preview.setText("尚未选择区域")
                self._set_video_status("ready", "先框选视频里的字幕区域")

    def _select_video_region(self) -> None:
        if self._video_monitoring:
            self._stop_video_monitoring()
        selector = RegionSelector()
        self._region_selector = selector
        selector.region_selected.connect(self._video_region_selected)
        selector.cancelled.connect(self._video_region_selection_cancelled)
        selector.destroyed.connect(lambda: setattr(self, "_region_selector", None))
        selector.show()
        selector.raise_()
        selector.activateWindow()

    def _video_region_selection_cancelled(self) -> None:
        self._region_selector = None

    def _start_text_selection(self) -> None:
        if QApplication.activeModalWidget() is not None:
            return
        if self._text_region_selector is not None:
            self._text_region_selector.raise_()
            self._text_region_selector.activateWindow()
            return
        if self._text_ocr_pending:
            self.toast.show_message("正在识别上一次框选的文字…", "info")
            return
        if self._video_monitoring:
            self._stop_video_monitoring()
        if self._speech_worker is not None and self._speech_worker.isRunning():
            self._stop_listening()
        if self._quick_popup is not None:
            self._quick_popup.hide()
        selector = RegionSelector(
            "拖动框选屏幕上的文字  ·  按 Esc 取消",
            min_width=12,
            min_height=8,
        )
        self._text_region_selector = selector
        selector.region_selected.connect(self._text_region_selected)
        selector.cancelled.connect(self._text_region_cancelled)
        selector.destroyed.connect(lambda: setattr(self, "_text_region_selector", None))
        selector.show()
        selector.raise_()
        selector.activateWindow()

    def _text_region_cancelled(self) -> None:
        self._text_region_selector = None

    def _text_region_selected(self, region: QRect) -> None:
        self._text_region_selector = None
        QTimer.singleShot(100, lambda: self._capture_text_region(region))

    def _capture_text_region(self, region: QRect) -> None:
        pixmap = self._capture_region_pixmap(region)
        if pixmap is None or pixmap.isNull():
            self._text_ocr_pending = False
            self._show_quick_popup(region)
            if self._quick_popup is not None:
                self._quick_popup.set_content(
                    "",
                    "无法识别",
                    "无法截取该区域，请重新框选。",
                )
            return
        self._quick_region = region
        self._show_quick_popup(region)
        if self._quick_popup is not None:
            self._quick_popup.set_content(
                "",
                "正在识别…",
                "正在识别选区文字…",
            )
        worker = self._text_ocr_worker
        if worker is None:
            worker = SubtitleOcrWorker(self)
            worker.text_ready.connect(self._text_ocr_ready)
            worker.error.connect(self._text_ocr_error)
            self._text_ocr_worker = worker
            worker.start()
        elif not worker.isRunning():
            worker.start()
        self._text_ocr_pending = True
        worker.submit(pixmap.toImage())

    def _text_ocr_ready(self, text: str) -> None:
        if not self._text_ocr_pending:
            return
        self._text_ocr_pending = False
        text = text.strip()
        if not text:
            if self._quick_popup is not None:
                self._quick_popup.set_error(
                    "选区内没有识别到文字，请调整选区后重试。"
                )
            return
        self._quick_source_text = text
        if self._quick_popup is None:
            if self._quick_region is not None:
                self._show_quick_popup(self._quick_region)
        if self._quick_popup is not None:
            self._quick_popup.set_content(
                text,
                "正在翻译…",
                "正在翻译选区文字…",
            )
        QTimer.singleShot(
            80,
            lambda: self._start_translation("quick", user_initiated=False),
        )

    def _text_ocr_error(self, message: str) -> None:
        if not self._text_ocr_pending:
            return
        self._text_ocr_pending = False
        if self._quick_popup is not None:
            self._quick_popup.set_error(message)
        else:
            self.toast.show_message(message, "error", 4200)

    def _show_quick_popup(self, region: QRect) -> None:
        if self._quick_popup is None:
            self._quick_popup = QuickTranslationPopup()
            self._quick_popup.speak_requested.connect(self._speak_quick_text)
        self._quick_popup.show_for_region(region)

    def _speak_quick_text(self, text: str) -> None:
        if text.strip():
            self.speaker.speak(text.strip(), self._target_code())

    def _video_region_selected(self, region: QRect) -> None:
        self._region_selector = None
        if region.width() < 80 or region.height() < 22:
            self.toast.show_message("选择区域太小，请重新框选字幕条。", "info")
            return
        self._video_region = region
        self.settings["video_region"] = [
            region.x(),
            region.y(),
            region.width(),
            region.height(),
        ]
        self._save_settings_quietly()
        self._update_video_region_ui()
        QTimer.singleShot(120, self._refresh_video_preview)
        self.toast.show_message("字幕区域已选好，正在开始识别。")
        QTimer.singleShot(220, self._start_video_monitoring)

    def _update_video_region_ui(self) -> None:
        region = self._video_region
        if region is None:
            self.video_region_label.setText("尚未选择字幕区域")
            self.video_start_button.setEnabled(False)
            return
        self.video_region_label.setText(
            f"识别区域：{region.width()} × {region.height()}  ·  "
            f"位置 {region.x()}, {region.y()}"
        )
        self.video_start_button.setEnabled(True)

    def _capture_video_pixmap(self):
        region = self._video_region
        if region is None:
            return None
        return self._capture_region_pixmap(region)

    def _capture_region_pixmap(self, region: QRect):
        screen = QApplication.screenAt(region.center()) or QApplication.primaryScreen()
        if screen is None:
            return None
        screen_geometry = screen.geometry()
        local = region.translated(-screen_geometry.x(), -screen_geometry.y())
        pixmap = screen.grabWindow(
            0,
            local.x(),
            local.y(),
            local.width(),
            local.height(),
        )
        if pixmap.isNull():
            return None
        return pixmap

    def _refresh_video_preview(self) -> None:
        if self._video_source_mode() != "subtitle":
            return
        pixmap = self._capture_video_pixmap()
        if pixmap is None:
            self.video_preview.setPixmap(QPixmap())
            self.video_preview.setText("无法截取该区域")
            return
        scaled = pixmap.scaled(
            self.video_preview.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.video_preview.setPixmap(scaled)

    def _toggle_video_monitoring(self) -> None:
        if self._video_monitoring:
            self._stop_video_monitoring()
        elif self._video_source_mode() == "audio":
            self._start_audio_monitoring()
        else:
            self._start_video_monitoring()

    def _start_video_monitoring(self) -> None:
        if self._video_source_mode() != "subtitle":
            return
        if self._video_region is None:
            self.toast.show_message("请先点击“框选字幕区域”。", "info")
            return
        if self._video_monitoring:
            return
        if self._ocr_worker is None or not self._ocr_worker.isRunning():
            worker = SubtitleOcrWorker(self)
            worker.text_ready.connect(self._video_ocr_ready)
            worker.error.connect(self._video_ocr_error)
            self._ocr_worker = worker
            worker.start()
        self._video_monitoring = True
        self._last_video_ocr_key = ""
        self._last_video_translated_source = ""
        self._audio_detected_language = ""
        self._video_history = []
        self.video_debounce_timer.stop()
        self.video_start_button.setText("停止识别")
        self.video_headline.setText("正在实时识别字幕")
        self.video_hint.setText("保持字幕区域完整可见；识别到新字幕后会自动翻译。")
        self._set_video_status("busy", "正在监听字幕…")
        if self.video_overlay_check.isChecked():
            self._show_video_overlay()
        self.video_capture_timer.start()
        QTimer.singleShot(120, self._video_capture_tick)

    def _start_audio_monitoring(self) -> None:
        if self._video_monitoring:
            return
        if (
            importlib.util.find_spec("soundcard") is None
            or (
                not whisper_is_available()
                and importlib.util.find_spec("vosk") is None
            )
        ):
            self.toast.show_message(
                "声音转写组件未安装，请运行 pip install -r requirements.txt。",
                "error",
                4200,
            )
            return
        source = self._source_code()
        if not whisper_is_available() and source not in {"auto", "en"}:
            self.toast.show_message(
                "Whisper 多语言模型尚未安装，当前只能使用英语 Vosk。"
                "请运行 python scripts/install_whisper_model.py。",
                "error",
                4600,
            )
            return
        language = "auto" if source == "auto" else source
        transcriber = SystemAudioTranscriber(language, self)
        transcriber.transcript_ready.connect(self._audio_transcript_ready)
        transcriber.status_changed.connect(self._audio_status_changed)
        transcriber.error.connect(self._audio_error)
        self._audio_transcriber = transcriber
        self._video_monitoring = True
        self._last_video_ocr_key = ""
        self._last_video_translated_source = ""
        self._audio_detected_language = ""
        self._video_history = []
        self.video_debounce_timer.stop()
        self.video_start_button.setText("停止识别")
        self.video_headline.setText("正在监听电脑声音")
        self.video_hint.setText(
            "请正常播放视频声音；程序会按自然停顿自动断句、识别并翻译。"
        )
        self.video_engine_pill.setText(
            "Whisper · 正在启动" if whisper_is_available() else "Vosk · 正在启动"
        )
        self._set_video_status(
            "busy",
            "正在加载本地 Whisper 多语言模型…"
            if whisper_is_available()
            else "正在加载本地 Vosk 语音模型…",
        )
        if self.video_overlay_check.isChecked():
            self._show_video_overlay()
            if self._overlay is not None:
                self._overlay.set_content(
                    "正在监听电脑声音…",
                    "无需字幕，语音会在本机转写后自动翻译",
                )
        transcriber.start()

    def _audio_transcript_ready(self, text: str, language_code: str) -> None:
        if not self._video_monitoring:
            return
        detected = app_language_from_asr(language_code)
        if detected != "auto":
            self._audio_detected_language = detected
        language = language_label(detected) if detected != "auto" else "自动识别"
        engine = (
            self._audio_transcriber.device_label
            if self._audio_transcriber is not None
            else "Whisper"
        )
        self._accept_video_transcript(text, f"{engine} · {language}")

    def _audio_status_changed(self, message: str) -> None:
        if not self._video_monitoring:
            return
        self._set_video_status("busy", message)
        self.video_hint.setText(message)
        transcriber = self._audio_transcriber
        if transcriber is not None and transcriber.device_label:
            self.video_engine_pill.setText(
                f"{transcriber.device_label} · 本地"
            )

    def _audio_error(self, message: str) -> None:
        self._stop_video_monitoring()
        self._set_video_status("error", "声音转写失败", message)
        self.toast.show_message(message, "error", 5200)

    def _stop_video_monitoring(self, hide_overlay: bool = True) -> None:
        if not self._video_monitoring:
            return
        self._video_monitoring = False
        self.video_capture_timer.stop()
        self.video_debounce_timer.stop()
        worker = self._ocr_worker
        self._ocr_worker = None
        if worker is not None:
            worker.stop()
            if worker.wait(2500):
                worker.deleteLater()
            else:
                self._retired_ocr_workers.add(worker)
                worker.finished.connect(lambda item=worker: self._release_ocr_worker(item))
        audio = self._audio_transcriber
        self._audio_transcriber = None
        if audio is not None:
            audio.stop()
        if hide_overlay and self._overlay is not None:
            self._overlay.hide()
        self.video_start_button.setText("开始识别")
        self._update_video_mode_ui()
        stopped = (
            "声音转写已停止"
            if self._video_source_mode() == "audio"
            else "字幕识别已停止"
        )
        self._set_video_status("ready", stopped)

    def _release_ocr_worker(self, worker: SubtitleOcrWorker) -> None:
        self._retired_ocr_workers.discard(worker)
        worker.deleteLater()

    def _video_capture_tick(self) -> None:
        if not self._video_monitoring or self._video_source_mode() != "subtitle":
            return
        pixmap = self._capture_video_pixmap()
        if pixmap is None:
            self._set_video_status("error", "无法截取字幕区域")
            return
        scaled = pixmap.scaled(
            self.video_preview.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.video_preview.setPixmap(scaled)
        worker = self._ocr_worker
        if worker is not None and worker.isRunning():
            worker.submit(pixmap.toImage())

    def _video_ocr_ready(self, text: str) -> None:
        if not self._video_monitoring:
            return
        self._accept_video_transcript(text, "本地 OCR")

    def _accept_video_transcript(self, text: str, source_label: str) -> None:
        text = text.strip()
        if not text:
            return
        key = re.sub(r"[\W_]+", "", text.lower())
        if not key:
            return
        if key == self._last_video_ocr_key:
            return
        if (
            self._last_video_ocr_key
            and SequenceMatcher(None, key, self._last_video_ocr_key).ratio() > 0.985
        ):
            return
        self._last_video_ocr_key = key
        if not self._video_history or self._video_history[-1] != text:
            self._video_history.append(text)
            self._video_history = self._video_history[-4:]
        self.video_source_edit.setPlainText(text)
        self.video_source_badge.setText(source_label)
        self.video_translate_button.setEnabled(True)
        self._set_video_status("busy", "检测到新内容，准备翻译…")
        if self.video_overlay_check.isChecked():
            self._show_video_overlay()
            if self._overlay is not None:
                self._overlay.set_content(text, "正在翻译…")
        self.video_debounce_timer.start()

    def _video_ocr_error(self, message: str) -> None:
        self._set_video_status("error", "字幕识别失败", message)
        self.toast.show_message(message, "error", 4200)

    def _translate_video_subtitle(self) -> None:
        if not self._video_monitoring:
            return
        text = self.video_source_edit.toPlainText().strip()
        if not text or text == self._last_video_translated_source:
            return
        self._start_translation("video", user_initiated=False)

    def _video_text_changed(self) -> None:
        self.video_translate_button.setEnabled(
            bool(self.video_source_edit.toPlainText().strip())
        )

    def _video_overlay_toggled(self, enabled: bool) -> None:
        self.settings["overlay_enabled"] = enabled
        self._save_settings_quietly()
        if not self._video_monitoring:
            return
        if enabled:
            self._show_video_overlay()
        elif self._overlay is not None:
            self._overlay.hide()

    def _show_video_overlay(self) -> None:
        created = self._overlay is None
        if created:
            self._overlay = SubtitleOverlay()
            self._overlay.set_content("正在监听字幕…", "等待画面中出现新的字幕")
        raw_pos = self.settings.get("overlay_pos", [])
        positioned = False
        if created and isinstance(raw_pos, list) and len(raw_pos) == 2:
            try:
                x, y = int(raw_pos[0]), int(raw_pos[1])
                for screen in QApplication.screens():
                    if screen.availableGeometry().contains(QRect(x, y, 200, 100)):
                        self._overlay.move(x, y)
                        positioned = True
                        break
            except (TypeError, ValueError):
                pass
        if created and not positioned:
            if self._video_source_mode() == "audio":
                self._overlay.place_default()
            elif self._video_region is not None:
                self._overlay.place_away_from(self._video_region)
        self._overlay.show()
        self._overlay.raise_()

    def _source_text_changed(self) -> None:
        text = self.source_edit.toPlainText()
        count = len(text)
        self.char_count.setText(f"{count} / {self.MAX_CHARS}")
        color = theme.RED if count > self.MAX_CHARS else theme.FAINT
        self.char_count.setStyleSheet(f"color:{color};")
        self.translate_button.setEnabled(bool(text.strip()) and not self._translating)
        if (
            self.settings.get("auto_translate")
            and self._mode == 0
            and text.strip()
            and text.strip() != self._last_text_translated
        ):
            self.auto_timer.start()

    def _voice_text_changed(self) -> None:
        self.voice_translate_button.setEnabled(
            bool(self.voice_source_edit.toPlainText().strip())
        )

    def _auto_translate(self) -> None:
        if (
            self._mode == 0
            and self.auto_translate_check.isChecked()
            and self.source_edit.toPlainText().strip()
        ):
            self._start_translation("text", user_initiated=False)

    def _translate_current(self, user_initiated: bool = True) -> None:
        context = ("text", "voice", "video")[self._mode]
        self._start_translation(context, user_initiated)

    def _start_translation(self, context: str, user_initiated: bool = True) -> None:
        if context == "text":
            text = self.source_edit.toPlainText().strip()
            source = self._source_code()
        elif context == "quick":
            text = self._quick_source_text.strip()
            source = self._source_code()
        elif context == "voice":
            text = self.voice_source_edit.toPlainText().strip()
            source = self._speech_source_culture or self._source_code()
        else:
            text = self.video_source_edit.toPlainText().strip()
            source = self._source_code()
            if (
                source == "auto"
                and self._video_source_mode() == "audio"
                and self._audio_detected_language
            ):
                source = self._audio_detected_language

        if not text:
            if user_initiated:
                self.toast.show_message("请先输入或识别一段文字。", "info")
            return
        if len(text) > self.MAX_CHARS:
            self.toast.show_message("内容超过 5000 个字符，请分段翻译。", "error")
            return
        if source == "auto" and context == "voice":
            source = self.recognizer_cultures[0] if self.recognizer_cultures else "auto"

        engine = str(self.settings.get("engine", "deepseek"))
        key = ""
        if engine == "deepseek":
            key = reveal_secret(str(self.settings.get("deepseek_api_key", "")))
        elif engine == "openai":
            key = reveal_secret(str(self.settings.get("openai_api_key", "")))
        if engine in {"deepseek", "openai"} and not key:
            message = f"{ENGINE_LABELS.get(engine, engine)} 还没有配置 API Key。"
            self.toast.show_message(message, "error")
            if context == "text":
                self._set_text_status("error", "请先配置翻译引擎")
            elif context == "voice":
                self._set_voice_status("error", "请先配置翻译引擎")
            elif context == "quick":
                if self._quick_popup is not None:
                    self._quick_popup.set_error(message)
            else:
                self._set_video_status("error", "请先配置翻译引擎")
            if user_initiated:
                QTimer.singleShot(250, self._open_settings)
            return

        if context == "quick":
            self._quick_seq += 1
            request_id = self._quick_seq
        else:
            self._request_seq += 1
            request_id = self._request_seq
            self._translating = True
        target = self._target_code()
        translation_context = ""
        if context == "video":
            previous_lines = [
                line for line in self._video_history if line != text
            ][-3:]
            translation_context = "\n".join(previous_lines)
        engine_label = ENGINE_LABELS.get(engine, engine)
        if context == "text":
            self.translate_button.setEnabled(False)
            self.translate_button.setText("翻译中…")
            self._set_text_status("busy", f"正在使用 {engine_label} 翻译…")
        elif context == "voice":
            self.voice_translate_button.setEnabled(False)
            self.voice_translate_button.setText("翻译中…")
            self._set_voice_status("busy", f"正在使用 {engine_label} 翻译…")
        elif context == "quick":
            if self._quick_popup is not None:
                self._quick_popup.set_content(
                    self._quick_source_text,
                    "正在翻译…",
                    f"正在使用 {engine_label} 翻译…",
                )
        else:
            self.video_translate_button.setEnabled(False)
            self.video_translate_button.setText("翻译中…")
            self._set_video_status("busy", f"正在翻译新字幕 · {engine_label}")

        worker = TranslateWorker(
            request_id,
            context,
            self.settings,
            text,
            source,
            target,
            translation_context,
            self,
        )
        worker.result_ready.connect(self._translation_succeeded)
        worker.error_ready.connect(self._translation_failed)
        worker.finished.connect(lambda: self._finish_worker(worker))
        self._workers.add(worker)
        worker.start()

    def _translation_succeeded(
        self, request_id: int, context: str, result: TranslationResult
    ) -> None:
        if context == "quick":
            if request_id != self._quick_seq:
                return
        else:
            if request_id != self._request_seq:
                return
            self._translating = False
        target_text = ""
        if context == "text":
            self.text_result_edit.setPlainText(result.text)
            self.text_provider_badge.setText(result.provider)
            self.text_provider_badge.setVisible(True)
            if self._source_code() == "auto" and result.detected_language:
                self.text_source_badge.setText(
                    f"自动识别 · {language_label(result.detected_language)}"
                )
            self.translate_button.setText("翻译")
            self.translate_button.setEnabled(bool(self.source_edit.toPlainText().strip()))
            self._set_text_status("success", f"翻译完成 · {result.provider}")
            self._last_text_translated = self.source_edit.toPlainText().strip()
            target_text = self.text_result_edit.toPlainText()
        elif context == "quick":
            if self._quick_popup is not None:
                self._quick_popup.set_content(
                    self._quick_source_text,
                    result.text,
                    f"翻译完成 · {result.provider}",
                    result.provider,
                )
            target_text = result.text
        elif context == "voice":
            self.voice_result_edit.setPlainText(result.text)
            self.voice_provider_badge.setText(result.provider)
            self.voice_provider_badge.setVisible(True)
            if result.detected_language:
                self.voice_source_badge.setText(
                    f"语音 · {language_label(result.detected_language)}"
                )
            self.voice_translate_button.setText("重新翻译")
            self.voice_translate_button.setEnabled(True)
            self.voice_headline.setText("翻译完成，可以继续说话")
            self.voice_hint.setText("识别结果可以修改后点“重新翻译”")
            self._set_voice_status("success", f"翻译完成 · {result.provider}")
            target_text = self.voice_result_edit.toPlainText()
        else:
            self.video_result_edit.setPlainText(result.text)
            self.video_provider_badge.setText(result.provider)
            self.video_provider_badge.setVisible(True)
            self.video_translate_button.setText("重新翻译")
            self.video_translate_button.setEnabled(True)
            self._set_video_status("success", f"字幕已翻译 · {result.provider}")
            self._last_video_translated_source = self.video_source_edit.toPlainText().strip()
            target_text = self.video_result_edit.toPlainText()
            if (
                self._video_monitoring
                and self._overlay is not None
                and self.video_overlay_check.isChecked()
            ):
                self._overlay.set_content(
                    self.video_source_edit.toPlainText().strip(),
                    target_text,
                )
                self._show_video_overlay()
        if target_text and self.auto_speak_check.isChecked():
            target_lcid = sapi_lcid(self._target_code())
            if (
                context != "video"
                and target_lcid is not None
                and target_lcid in self.installed_voice_languages
            ):
                self.speaker.speak(target_text, self._target_code())

    def _translation_failed(self, request_id: int, context: str, message: str) -> None:
        if context == "quick":
            if request_id != self._quick_seq:
                return
            if self._quick_popup is not None:
                self._quick_popup.set_error(message)
            self.toast.show_message(message, "error", 5200)
            if "API Key" in message and not self._settings_open:
                QTimer.singleShot(300, self._open_settings)
            return
        if request_id != self._request_seq:
            return
        self._translating = False
        self.translate_button.setText("翻译")
        self.translate_button.setEnabled(bool(self.source_edit.toPlainText().strip()))
        self.voice_translate_button.setText("重新翻译")
        self.voice_translate_button.setEnabled(
            bool(self.voice_source_edit.toPlainText().strip())
        )
        self.video_translate_button.setText("重新翻译")
        self.video_translate_button.setEnabled(
            bool(self.video_source_edit.toPlainText().strip())
        )
        if context == "text":
            self._set_text_status("error", "翻译失败", message)
        elif context == "voice":
            self._set_voice_status("error", "翻译失败", message)
        else:
            self._set_video_status("error", "字幕翻译失败", message)
            if (
                self._video_monitoring
                and self._overlay is not None
                and self.video_overlay_check.isChecked()
            ):
                self._overlay.set_content(
                    self.video_source_edit.toPlainText().strip(),
                    "翻译失败，请检查网络或引擎设置",
                )
        self.toast.show_message(message, "error", 5200)
        if "API Key" in message and not self._settings_open:
            QTimer.singleShot(300, self._open_settings)

    def _finish_worker(self, worker: TranslateWorker) -> None:
        self._workers.discard(worker)
        worker.deleteLater()

    def _set_text_status(self, kind: str, message: str, tooltip: str = "") -> None:
        self._set_status(self.text_status_dot, self.text_status, kind, message, tooltip)

    def _set_voice_status(self, kind: str, message: str, tooltip: str = "") -> None:
        self._set_status(self.voice_status_dot, self.voice_status, kind, message, tooltip)

    def _set_video_status(self, kind: str, message: str, tooltip: str = "") -> None:
        self._set_status(self.video_status_dot, self.video_status, kind, message, tooltip)

    @staticmethod
    def _set_status(
        dot: QFrame,
        label: QLabel,
        kind: str,
        message: str,
        tooltip: str = "",
    ) -> None:
        colors = {
            "ready": theme.FAINT,
            "busy": theme.ACCENT,
            "success": theme.GREEN,
            "error": theme.RED,
        }
        color = colors.get(kind, theme.FAINT)
        dot.setStyleSheet(f"background:{color};border-radius:4px;")
        label.setText(message)
        label.setToolTip(tooltip)

    def _swap_languages(self) -> None:
        source = self._source_code()
        target = self._target_code()
        if source == "auto":
            new_source = target
            new_target = "zh-CN" if target != "zh-CN" else "en"
        else:
            new_source, new_target = target, source
        self.source_combo.blockSignals(True)
        self.target_combo.blockSignals(True)
        self.source_combo.setCurrentIndex(max(0, self.source_combo.findData(new_source)))
        self.target_combo.setCurrentIndex(max(0, self.target_combo.findData(new_target)))
        self.source_combo.blockSignals(False)
        self.target_combo.blockSignals(False)
        self._language_changed()
        if self._mode == 0 and self.source_edit.toPlainText().strip():
            self._start_translation("text", user_initiated=False)

    def _paste_text(self) -> None:
        text = QApplication.clipboard().text()
        if not text:
            self.toast.show_message("剪贴板里没有文字。", "info")
            return
        self.source_edit.setPlainText(text)
        self.source_edit.setFocus()

    def _clear_text(self) -> None:
        self.source_edit.clear()
        self.text_result_edit.clear()
        self.text_provider_badge.setVisible(False)
        self._last_text_translated = ""
        self._set_text_status("ready", "文字翻译已就绪")

    def _copy_current(self) -> None:
        if self._mode == 0:
            self._copy_result()
        elif self._mode == 1:
            self._copy_voice_result()
        else:
            self._copy_video_result()

    def _copy_result(self) -> None:
        text = self.text_result_edit.toPlainText().strip()
        if not text:
            self.toast.show_message("还没有可复制的译文。", "info")
            return
        QApplication.clipboard().setText(text)
        self.toast.show_message("译文已复制。")

    def _copy_voice_result(self) -> None:
        text = self.voice_result_edit.toPlainText().strip()
        if not text:
            self.toast.show_message("还没有可复制的译文。", "info")
            return
        QApplication.clipboard().setText(text)
        self.toast.show_message("译文已复制。")

    def _copy_video_result(self) -> None:
        text = self.video_result_edit.toPlainText().strip()
        if not text:
            self.toast.show_message("还没有可复制的字幕译文。", "info")
            return
        QApplication.clipboard().setText(text)
        self.toast.show_message("字幕译文已复制。")

    def _speak_current_result(self) -> None:
        if self._mode == 0:
            self._speak_result()
        elif self._mode == 1:
            self._speak_voice_result()
        else:
            self._speak_video_result()

    def _speak_result(self) -> None:
        text = self.text_result_edit.toPlainText().strip()
        if not text:
            self.toast.show_message("还没有可朗读的译文。", "info")
            return
        self.speaker.speak(text, self._target_code())

    def _speak_voice_result(self) -> None:
        text = self.voice_result_edit.toPlainText().strip()
        if not text:
            self.toast.show_message("还没有可朗读的译文。", "info")
            return
        self.speaker.speak(text, self._target_code())

    def _speak_video_result(self) -> None:
        text = self.video_result_edit.toPlainText().strip()
        if not text:
            self.toast.show_message("还没有可朗读的字幕译文。", "info")
            return
        self.speaker.speak(text, self._target_code())

    def _speak_source(self) -> None:
        text = self.source_edit.toPlainText().strip()
        if not text:
            self.toast.show_message("还没有可朗读的原文。", "info")
            return
        source = self._source_code()
        if source == "auto":
            source = detect_language_heuristic(text)
        self.speaker.speak(text, source)

    def _focus_source(self) -> None:
        if self._mode == 0:
            self.source_edit.setFocus()
        elif self._mode == 1:
            self.voice_source_edit.setFocus()
        else:
            self.video_source_edit.setFocus()

    def _toggle_listening(self) -> None:
        if self._speech_worker is not None and self._speech_worker.isRunning():
            self._stop_listening()
            return
        self._start_listening()

    def _start_listening(self) -> None:
        if not self.recognizer_cultures:
            self.toast.show_message(
                "本机没有语音识别引擎，请先在 Windows 设置中安装。",
                "error",
            )
            return
        source = self._source_code()
        culture = speech_culture_for_source(source, self.recognizer_cultures)
        if culture is None:
            requested = language_label(source)
            self.toast.show_message(
                f"系统没有安装{requested}语音识别包。"
                "可在 Windows“时间和语言 → 语音”中添加。",
                "error",
                4200,
            )
            return
        self._speech_source_culture = culture
        self.settings["speech_lang"] = culture
        self._save_settings_quietly()
        self.mic_button.set_listening(True)
        self.waveform.set_active(True)
        self.voice_stop_button.setVisible(True)
        self.voice_headline.setText("正在聆听…")
        self.voice_hint.setText("请自然地说完一句话，停顿后会自动结束")
        self._set_voice_status("busy", "正在识别语音…")
        self.voice_translate_button.setEnabled(False)

        worker = RecognitionWorker(culture, 20, self)
        worker.recognized.connect(self._recognition_recognized)
        worker.failed.connect(self._recognition_failed)
        worker.cancelled.connect(self._recognition_cancelled)
        worker.finished.connect(self._recognition_finished)
        self._speech_worker = worker
        worker.start()

    def _stop_listening(self) -> None:
        worker = self._speech_worker
        if worker is not None and worker.isRunning():
            self.voice_hint.setText("正在停止聆听…")
            worker.cancel()

    def _recognition_recognized(self, text: str, culture: str, confidence: float) -> None:
        self._speech_source_culture = culture
        self.voice_source_edit.setPlainText(text)
        language = language_for_culture(culture)
        label = language.label if language else culture
        self.voice_source_badge.setText(f"语音 · {label}")
        self.voice_headline.setText("已识别，正在翻译…")
        self.voice_hint.setText(f"识别引擎：{label}")
        self._set_voice_status("success", f"已识别 · 置信度 {confidence:.0%}")
        self._start_translation("voice", user_initiated=False)

    def _recognition_failed(self, message: str) -> None:
        self._set_voice_status("error", "语音识别失败", message)
        self.voice_headline.setText("没有听清，请再试一次")
        self.voice_hint.setText(message)
        self.toast.show_message(message, "error", 4200)

    def _recognition_cancelled(self) -> None:
        self._set_voice_status("ready", "已停止聆听")
        self.voice_headline.setText("点击话筒，继续说话")
        self.voice_hint.setText("说完停顿一下，识别会自动结束")

    def _recognition_finished(self) -> None:
        worker = self._speech_worker
        self._speech_worker = None
        if worker is not None:
            worker.deleteLater()
        self.mic_button.set_listening(False)
        self.waveform.set_active(False)
        self.voice_stop_button.setVisible(False)
        if self.voice_headline.text() == "正在聆听…":
            self.voice_headline.setText("点击话筒，开始说话")
            self.voice_hint.setText("说完停顿一下，识别会自动结束")
        self.voice_translate_button.setEnabled(
            bool(self.voice_source_edit.toPlainText().strip())
        )

    def _escape(self) -> None:
        self.speaker.stop()
        if self._speech_worker is not None and self._speech_worker.isRunning():
            self._stop_listening()

    def _on_speaker_error(self, message: str) -> None:
        self.toast.show_message(message, "error", 4200)

    def _open_settings(self) -> None:
        if self._settings_open:
            return
        self._settings_open = True
        try:
            dialog = SettingsDialog(
                self.settings,
                self.installed_recognizers,
                self.installed_voices,
                self,
            )
            if dialog.exec_() == SettingsDialog.Accepted:
                self.settings = dict(dialog.settings)
                save_settings(self.settings)
                self.auto_translate_check.blockSignals(True)
                self.auto_speak_check.blockSignals(True)
                self.auto_translate_check.setChecked(
                    bool(self.settings.get("auto_translate", False))
                )
                self.auto_speak_check.setChecked(
                    bool(self.settings.get("auto_speak", True))
                )
                self.auto_translate_check.blockSignals(False)
                self.auto_speak_check.blockSignals(False)
                self._update_engine_badge()
                self.toast.show_message("设置已保存。")
        finally:
            self._settings_open = False

    def _save_settings_quietly(self) -> None:
        try:
            save_settings(self.settings)
        except OSError:
            pass

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.auto_timer.stop()
        self.speaker.stop()
        if self._hotkey_filter is not None:
            self._hotkey_filter.unregister()
            self._hotkey_filter = None
        if self._text_region_selector is not None:
            self._text_region_selector.close()
            self._text_region_selector = None
        if self._text_ocr_worker is not None:
            self._text_ocr_worker.stop()
            self._text_ocr_worker.wait(2500)
            self._text_ocr_worker.deleteLater()
            self._text_ocr_worker = None
        if self._quick_popup is not None:
            self._quick_popup.close()
            self._quick_popup.deleteLater()
            self._quick_popup = None
        if self._video_monitoring:
            self._stop_video_monitoring()
        if self._speech_worker is not None and self._speech_worker.isRunning():
            self._speech_worker.cancel()
            self._speech_worker.wait(800)
        for worker in list(self._workers):
            worker.wait(600)
        for worker in list(self._retired_ocr_workers):
            worker.wait(3000)
        if self._overlay is not None:
            self.settings["overlay_pos"] = [
                self._overlay.pos().x(),
                self._overlay.pos().y(),
            ]
            self._overlay.close()
            self._overlay.deleteLater()
            self._overlay = None
        if self._video_region is not None:
            self.settings["video_region"] = [
                self._video_region.x(),
                self._video_region.y(),
                self._video_region.width(),
                self._video_region.height(),
            ]
        self.settings["geometry"] = bytes(self.saveGeometry().toBase64()).decode("ascii")
        self.settings["source_lang"] = self._source_code()
        self.settings["target_lang"] = self._target_code()
        self.settings["auto_translate"] = self.auto_translate_check.isChecked()
        self.settings["auto_speak"] = self.auto_speak_check.isChecked()
        self._save_settings_quietly()
        event.accept()

