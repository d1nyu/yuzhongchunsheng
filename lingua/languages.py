"""Complete language catalog and language metadata."""

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


# Google-supported language codes, with frequently used languages first.
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
    Language("uk", "乌克兰语", "Ukrainian", "uk", 0x0422, ("uk-UA",)),
    Language("af", "南非荷兰语", "Afrikaans", "af"),
    Language("sq", "阿尔巴尼亚语", "Albanian", "sq"),
    Language("am", "阿姆哈拉语", "Amharic", "am"),
    Language("hy", "亚美尼亚语", "Armenian", "hy"),
    Language("as", "阿萨姆语", "Assamese", "as"),
    Language("ay", "艾马拉语", "Aymara", "ay"),
    Language("az", "阿塞拜疆语", "Azerbaijani", "az"),
    Language("bm", "班巴拉语", "Bambara", "bm"),
    Language("eu", "巴斯克语", "Basque", "eu"),
    Language("be", "白俄罗斯语", "Belarusian", "be"),
    Language("bn", "孟加拉语", "Bengali", "bn"),
    Language("bho", "博杰普尔语", "Bhojpuri", "bho"),
    Language("bs", "波斯尼亚语", "Bosnian", "bs"),
    Language("bg", "保加利亚语", "Bulgarian", "bg"),
    Language("ca", "加泰罗尼亚语", "Catalan", "ca"),
    Language("ceb", "宿务语", "Cebuano", "ceb"),
    Language("co", "科西嘉语", "Corsican", "co"),
    Language("hr", "克罗地亚语", "Croatian", "hr"),
    Language("cs", "捷克语", "Czech", "cs"),
    Language("da", "丹麦语", "Danish", "da"),
    Language("dv", "迪维希语", "Dhivehi", "dv"),
    Language("doi", "多格拉语", "Dogri", "doi"),
    Language("eo", "世界语", "Esperanto", "eo"),
    Language("et", "爱沙尼亚语", "Estonian", "et"),
    Language("ee", "埃维语", "Ewe", "ee"),
    Language("tl", "菲律宾语", "Filipino", "tl"),
    Language("fi", "芬兰语", "Finnish", "fi"),
    Language("fy", "弗里西语", "Frisian", "fy"),
    Language("gl", "加利西亚语", "Galician", "gl"),
    Language("ka", "格鲁吉亚语", "Georgian", "ka"),
    Language("el", "希腊语", "Greek", "el"),
    Language("gn", "瓜拉尼语", "Guarani", "gn"),
    Language("gu", "古吉拉特语", "Gujarati", "gu"),
    Language("ht", "海地克里奥尔语", "Haitian Creole", "ht"),
    Language("ha", "豪萨语", "Hausa", "ha"),
    Language("haw", "夏威夷语", "Hawaiian", "haw"),
    Language("he", "希伯来语", "Hebrew", "he"),
    Language("hi", "印地语", "Hindi", "hi"),
    Language("hmn", "苗语", "Hmong", "hmn"),
    Language("hu", "匈牙利语", "Hungarian", "hu"),
    Language("is", "冰岛语", "Icelandic", "is"),
    Language("ig", "伊博语", "Igbo", "ig"),
    Language("ilo", "伊洛卡诺语", "Ilocano", "ilo"),
    Language("ga", "爱尔兰语", "Irish", "ga"),
    Language("jw", "爪哇语", "Javanese", "jw"),
    Language("kn", "卡纳达语", "Kannada", "kn"),
    Language("kk", "哈萨克语", "Kazakh", "kk"),
    Language("km", "高棉语", "Khmer", "km"),
    Language("rw", "卢旺达语", "Kinyarwanda", "rw"),
    Language("gom", "孔卡尼语", "Konkani", "gom"),
    Language("kri", "克里奥尔语", "Krio", "kri"),
    Language("ku", "库尔德语（库尔曼吉）", "Kurdish (Kurmanji)", "ku"),
    Language("ckb", "库尔德语（索拉尼）", "Kurdish (Sorani)", "ckb"),
    Language("ky", "吉尔吉斯语", "Kyrgyz", "ky"),
    Language("lo", "老挝语", "Lao", "lo"),
    Language("la", "拉丁语", "Latin", "la"),
    Language("lv", "拉脱维亚语", "Latvian", "lv"),
    Language("ln", "林加拉语", "Lingala", "ln"),
    Language("lt", "立陶宛语", "Lithuanian", "lt"),
    Language("lg", "卢干达语", "Luganda", "lg"),
    Language("lb", "卢森堡语", "Luxembourgish", "lb"),
    Language("mk", "马其顿语", "Macedonian", "mk"),
    Language("mai", "迈蒂利语", "Maithili", "mai"),
    Language("mg", "马达加斯加语", "Malagasy", "mg"),
    Language("ms", "马来语", "Malay", "ms"),
    Language("ml", "马拉雅拉姆语", "Malayalam", "ml"),
    Language("mt", "马耳他语", "Maltese", "mt"),
    Language("mi", "毛利语", "Maori", "mi"),
    Language("mr", "马拉地语", "Marathi", "mr"),
    Language("mni-Mtei", "梅泰语（曼尼普尔）", "Meiteilon (Manipuri)", "mni-Mtei"),
    Language("lus", "米佐语", "Mizo", "lus"),
    Language("mn", "蒙古语", "Mongolian", "mn"),
    Language("my", "缅甸语", "Myanmar (Burmese)", "my"),
    Language("ne", "尼泊尔语", "Nepali", "ne"),
    Language("no", "挪威语", "Norwegian", "no"),
    Language("ny", "齐切瓦语", "Chichewa", "ny"),
    Language("or", "奥里亚语", "Odia (Oriya)", "or"),
    Language("om", "奥罗莫语", "Oromo", "om"),
    Language("ps", "普什图语", "Pashto", "ps"),
    Language("fa", "波斯语", "Persian", "fa"),
    Language("pa", "旁遮普语", "Punjabi", "pa"),
    Language("qu", "克丘亚语", "Quechua", "qu"),
    Language("ro", "罗马尼亚语", "Romanian", "ro"),
    Language("sm", "萨摩亚语", "Samoan", "sm"),
    Language("sa", "梵语", "Sanskrit", "sa"),
    Language("gd", "苏格兰盖尔语", "Scots Gaelic", "gd"),
    Language("nso", "塞佩迪语", "Sepedi", "nso"),
    Language("sr", "塞尔维亚语", "Serbian", "sr"),
    Language("st", "塞索托语", "Sesotho", "st"),
    Language("sn", "修纳语", "Shona", "sn"),
    Language("sd", "信德语", "Sindhi", "sd"),
    Language("si", "僧伽罗语", "Sinhala", "si"),
    Language("sk", "斯洛伐克语", "Slovak", "sk"),
    Language("sl", "斯洛文尼亚语", "Slovenian", "sl"),
    Language("so", "索马里语", "Somali", "so"),
    Language("su", "巽他语", "Sundanese", "su"),
    Language("sw", "斯瓦希里语", "Swahili", "sw"),
    Language("sv", "瑞典语", "Swedish", "sv"),
    Language("tg", "塔吉克语", "Tajik", "tg"),
    Language("ta", "泰米尔语", "Tamil", "ta"),
    Language("tt", "鞑靼语", "Tatar", "tt"),
    Language("te", "泰卢固语", "Telugu", "te"),
    Language("ti", "提格里尼亚语", "Tigrinya", "ti"),
    Language("ts", "聪加语", "Tsonga", "ts"),
    Language("tk", "土库曼语", "Turkmen", "tk"),
    Language("ak", "契维语", "Twi", "ak"),
    Language("ur", "乌尔都语", "Urdu", "ur"),
    Language("ug", "维吾尔语", "Uyghur", "ug"),
    Language("uz", "乌兹别克语", "Uzbek", "uz"),
    Language("cy", "威尔士语", "Welsh", "cy"),
    Language("xh", "科萨语", "Xhosa", "xh"),
    Language("yi", "意第绪语", "Yiddish", "yi"),
    Language("yo", "约鲁巴语", "Yoruba", "yo"),
    Language("zu", "祖鲁语", "Zulu", "zu"),
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
    normalized = (code or "").lower().replace("_", "-")
    for language in LANGUAGES:
        if language.code.lower() == normalized:
            return language.code
        if language.code.split("-")[0].lower() == normalized.split("-")[0]:
            return language.code
        if normalized in {alias.lower() for alias in language.speech_aliases}:
            return language.code
    return "auto"


def whisper_language(code: str) -> str:
    if not code or code == "auto":
        return ""
    overrides = {
        "zh-CN": "zh",
        "zh-TW": "zh",
        "mni-Mtei": "",
        "ckb": "",
    }
    return overrides.get(code, code.split("-")[0])


SOURCE_LANGUAGES = LANGUAGES
TARGET_LANGUAGES = tuple(item for item in LANGUAGES if item.code != "auto")
