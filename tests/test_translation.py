from __future__ import annotations

from unittest.mock import Mock

import requests

from lingua.languages import detect_language_heuristic
from lingua.ocr import combine_ocr_lines
from lingua.translation import TranslationService


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload


def test_google_translation_parsing():
    service = TranslationService({"engine": "google"})
    service.session.get = Mock(
        return_value=FakeResponse(
            payload=[
                [["Hello, ", "你好，"], ["world.", "世界。"]],
                None,
                "zh-CN",
            ]
        )
    )

    result = service.translate("你好，世界。", "auto", "en")

    assert result.text == "Hello, world."
    assert result.provider == "Google"
    assert result.detected_language == "zh-CN"


def test_google_falls_back_to_mymemory():
    service = TranslationService({"engine": "google"})
    service.session.get = Mock(
        side_effect=[
            requests.ConnectionError("connection timed out"),
            FakeResponse(
                payload={
                    "responseData": {"translatedText": "Hello"},
                    "responseStatus": 200,
                }
            ),
        ]
    )

    result = service.translate("你好", "zh-CN", "en")

    assert result.text == "Hello"
    assert result.provider == "MyMemory（备用）"


def test_deepseek_endpoint_and_parsing():
    service = TranslationService(
        {
            "engine": "deepseek",
            "deepseek_api_key": "test-key",
            "deepseek_base_url": "https://api.deepseek.com",
            "deepseek_model": "deepseek-chat",
        }
    )
    service.session.post = Mock(
        return_value=FakeResponse(
            payload={
                "choices": [
                    {"message": {"content": "Hello, nice to meet you."}}
                ]
            }
        )
    )

    result = service.translate(
        "你好，很高兴认识你。",
        "zh-CN",
        "en",
        context="A previous line about introducing a friend.",
    )

    assert result.text == "Hello, nice to meet you."
    assert result.provider == "DeepSeek"
    call = service.session.post.call_args
    assert call.args[0] == "https://api.deepseek.com/chat/completions"
    assert call.kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert call.kwargs["json"]["model"] == "deepseek-chat"
    user_prompt = call.kwargs["json"]["messages"][1]["content"]
    assert "Nearby context" in user_prompt
    assert "introducing a friend" in user_prompt


def test_language_heuristic():
    assert detect_language_heuristic("你好世界") == "zh-CN"
    assert detect_language_heuristic("こんにちは") == "ja"
    assert detect_language_heuristic("안녕하세요") == "ko"
    assert detect_language_heuristic("Hello world") == "en"


def test_ocr_line_merging():
    result = [
        [[[0, 0], [50, 0], [50, 20], [0, 20]], "Hello", 0.99],
        [[[52, 1], [110, 1], [110, 21], [52, 21]], "world", 0.98],
        [[[0, 28], [90, 28], [90, 48], [0, 48]], "第二行", 0.97],
    ]
    assert combine_ocr_lines(result) == "Hello world\n第二行"

