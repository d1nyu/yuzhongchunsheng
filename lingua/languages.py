"""Language metadata shared by the UI, translation and speech layers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    code: str
    label: str
    english: str
    google: str
    sapi_lcid: int | None = None
    speech_aliases: tuple[str, ...] = ()


LANGUAGES: tuple[Language, ...] = (
    Language("auto", "自动检测", "Detect language", "auto"),
    Language("zh-CN", "中文（简体）", "Chinese (Simplified)", "zh-CN", 0x0804, ("zh", "zh-Hans")),
    Language("zh-TW", "中文（繁体）", "Chinese (Traditional)", "zh-TW", 0x0404, ("zh-Hant",)),
    Language("en", "英语", "English", "en", 0x0409, ("en-US", "en-GB")),
    Language("ja", "日语", "Japanese", "ja", 0x0411, ("ja-JP",)),
    Language("ko", "韩语", "Korean", "ko", 0x0412, ("ko-KR",)),
    Language("fr", "法语", "French", "fr", 0x040C, ("fr-FR",)),
    Language("de", "德语", "German", "de", 0x0407, ("de-DE",)),
    Language("es", "西班牙语", "Spanish", "es", 0x040A, ("es-ES",)),
    Language("ru", "俄语", "Russian", "ru", 0x0419, ("ru-RU",)),
    Language("it", "意大利语", "Italian", "it", 0x0410, ("it-IT",)),
    Language("pt", "葡萄牙语", "Portuguese", "pt", 0x0416, ("pt-PT", "pt-BR")),
    Language("ar", "阿拉伯语", "Arabic", "ar", 0x0401, ("ar-SA",)),
    Language("th", "泰语", "Thai", "th", 0x041E, ("th-TH",)),
    Language("vi", "越南语", "Vietnamese", "vi", 0x042A, ("vi-VN",)),
    Language("id", "印尼语", "Indonesian", "id", 0x0421, ("id-ID",)),
    Language("tr", "土耳其语", "Turkish", "tr", 0x041F, ("tr-TR",)),
    Language("nl", "荷兰语", "Dutch", "nl", 0x0413, ("nl-NL",)),
    Language("pl", "波兰语", "Polish", "pl", 0x0415, ("pl-PL",)),
)

_BY_CODE = {item.code: item for item in LANGUAGES}


def get_language(code: str | None) -> Language:
    return _BY_CODE.get(code or "", _BY_CODE["auto"])


def language_label(code: str, english: bool = False) -> str:
    item = get_language(code)
    return item.english if english else item.label


def language_for_culture(culture: str) -> Language | None:
    for language in LANGUAGES:
        if language.code == culture:
            return language
        if culture.startswith(language.code + "-"):
            return language
        if culture in language.speech_aliases:
            return language
        if culture.split("-")[0] == language.code.split("-")[0]:
            return language
    return None


def google_code(code: str) -> str:
    return get_language(code).google


def sapi_lcid(code: str) -> int | None:
    return get_language(code).sapi_lcid


def speech_culture_for_source(source_code: str, installed: list[str]) -> str | None:
    """Find the best installed recognizer for a translation language."""
    if source_code == "auto":
        for preferred in ("zh-CN", "en-US", "en-GB", "ja-JP", "ko-KR"):
            if preferred in installed:
                return preferred
        return installed[0] if installed else None

    lang = get_language(source_code)
    candidates = (source_code, *lang.speech_aliases)
    for candidate in candidates:
        if candidate in installed:
            return candidate
    for candidate in installed:
        if candidate.split("-")[0] == source_code.split("-")[0]:
            return candidate
    return None


def detect_language_heuristic(text: str) -> str:
    """Small heuristic used only by engines that cannot auto-detect."""
    compact = text.strip()
    if not compact:
        return "en"
    if any("\u3040" <= char <= "\u30ff" for char in compact):
        return "ja"
    if any("\uac00" <= char <= "\ud7af" for char in compact):
        return "ko"
    if any("\u4e00" <= char <= "\u9fff" for char in compact):
        return "zh-CN"
    if any("\u0400" <= char <= "\u04ff" for char in compact):
        return "ru"
    if any("\u0600" <= char <= "\u06ff" for char in compact):
        return "ar"
    if any("\u0e00" <= char <= "\u0e7f" for char in compact):
        return "th"
    return "en"


def app_language_from_asr(code: str) -> str:
    mapping = {
        "zh": "zh-CN",
        "en": "en",
        "ja": "ja",
        "ko": "ko",
        "fr": "fr",
        "de": "de",
        "es": "es",
        "ru": "ru",
        "it": "it",
        "pt": "pt",
        "ar": "ar",
        "th": "th",
        "vi": "vi",
        "id": "id",
        "tr": "tr",
        "nl": "nl",
        "pl": "pl",
    }
    return mapping.get(code, "auto")


SOURCE_LANGUAGES = LANGUAGES
TARGET_LANGUAGES = tuple(item for item in LANGUAGES if item.code != "auto")

