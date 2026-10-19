from lingua.audio_translate import normalize_transcript
from lingua.languages import app_language_from_asr


def test_transcript_normalization():
    assert normalize_transcript("Let us go, together!") == "letusgotogether"
    assert normalize_transcript("  今天，天气真好。 ") == "今天天气真好"


def test_asr_language_mapping():
    assert app_language_from_asr("en") == "en"
    assert app_language_from_asr("zh") == "zh-CN"
    assert app_language_from_asr("unknown") == "auto"

