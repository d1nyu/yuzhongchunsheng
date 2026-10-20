import numpy as np

from lingua.audio_translate import (
    ASR_FRAME_SAMPLES,
    PauseSegmenter,
    normalize_transcript,
)
from lingua.languages import (
    LANGUAGES,
    TARGET_LANGUAGES,
    app_language_from_asr,
    whisper_language,
)


def test_transcript_normalization():
    assert normalize_transcript("Let us go, together!") == "letusgotogether"
    assert normalize_transcript("  今天，天气真好。 ") == "今天天气真好"


def test_asr_language_mapping():
    assert app_language_from_asr("en") == "en"
    assert app_language_from_asr("zh") == "zh-CN"
    assert app_language_from_asr("unknown") == "auto"
    assert whisper_language("auto") == ""
    assert whisper_language("zh-CN") == "zh"
    assert whisper_language("ja") == "ja"


def test_complete_language_catalog():
    assert len(LANGUAGES) >= 130
    assert len(TARGET_LANGUAGES) == len(LANGUAGES) - 1
    codes = {language.code for language in LANGUAGES}
    assert {"sw", "ta", "zu", "hi", "ar", "zh-CN"} <= codes


class _FakeVad:
    def is_speech(self, pcm: bytes, sample_rate: int) -> bool:
        samples = np.frombuffer(pcm, dtype=np.int16)
        return bool(samples.size and np.max(np.abs(samples)) > 1000)


def test_pause_segmenter_breaks_on_silence():
    segmenter = PauseSegmenter()
    segmenter._vad = _FakeVad()
    speech = np.full(ASR_FRAME_SAMPLES * 20, 0.08, dtype=np.float32)
    silence = np.zeros(ASR_FRAME_SAMPLES * 10, dtype=np.float32)
    assert segmenter.add_block(silence) is None
    assert segmenter.add_block(speech) is None
    assert segmenter.add_block(silence) is None
    assert segmenter.add_block(silence) is None
    segment = segmenter.add_block(silence)
    assert segment is not None
    assert segment.size >= ASR_FRAME_SAMPLES * 20

