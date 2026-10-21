"""Online translation engines with automatic fallback."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any

import requests

from .languages import detect_language_heuristic, get_language, google_code
from .secrets import reveal_secret


class TranslationError(RuntimeError):
    """A user-facing translation failure."""


@dataclass(frozen=True)
class TranslationResult:
    text: str
    provider: str
    detected_language: str


_NETWORK_MARKERS = (
    "timed out",
    "timeout",
    "connection",
    "getaddrinfo",
    "name resolution",
    "network",
    "ssl",
)


class TranslationService:
    def __init__(self, settings: dict[str, Any]):
        self.settings = dict(settings)
        self.engine = self.settings.get("engine", "google")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0 Safari/537.36 YuzhongChunsheng/1.0"
                ),
                "Accept": "application/json, text/plain, */*",
            }
        )

    def translate(
        self,
        text: str,
        source: str,
        target: str,
        context: str = "",
    ) -> TranslationResult:
        text = text.strip()
        if not text:
            raise TranslationError("请输入需要翻译的内容。")
        if len(text) > 5000:
            raise TranslationError("单次翻译最多支持 5000 个字符，请分段翻译。")
        if target == "auto":
            raise TranslationError("请选择目标语言。")
        if source == target and source != "auto":
            return TranslationResult(text, "无需翻译", source)

        if self.engine == "deepseek":
            return self._chat_translate(text, source, target, "deepseek", context)
        if self.engine == "openai":
            return self._chat_translate(text, source, target, "openai", context)
        if self.engine == "mymemory":
            return self._mymemory_with_fallback(text, source, target)
        return self._google_with_fallback(text, source, target)

    def _google_with_fallback(self, text: str, source: str, target: str) -> TranslationResult:
        try:
            return self._google_translate(text, source, target)
        except TranslationError as first_error:
            if len(text) <= 500:
                try:
                    result = self._mymemory_translate(text, source, target)
                    return TranslationResult(
                        result.text,
                        "MyMemory（备用）",
                        result.detected_language,
                    )
                except TranslationError:
                    pass
            raise TranslationError(
                f"{first_error}\n已尝试备用翻译服务，但仍然失败。"
            ) from None

    def _mymemory_with_fallback(self, text: str, source: str, target: str) -> TranslationResult:
        try:
            return self._mymemory_translate(text, source, target)
        except TranslationError as first_error:
            try:
                return self._google_translate(text, source, target)
            except TranslationError:
                raise TranslationError(
                    f"{first_error}\n已尝试备用翻译服务，但仍然失败。"
                ) from None

    def _google_translate(self, text: str, source: str, target: str) -> TranslationResult:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": google_code(source),
            "tl": google_code(target),
            "dt": "t",
            "q": text,
        }
        try:
            response = self.session.get(url, params=params, timeout=(6, 25))
        except requests.RequestException as exc:
            raise TranslationError(self._network_error(exc)) from None

        if response.status_code == 429:
            raise TranslationError("Google 免费翻译请求过于频繁，请稍后再试或切换翻译引擎。")
        if response.status_code >= 400:
            raise TranslationError(f"Google 翻译服务返回错误（HTTP {response.status_code}）。")
        try:
            payload = response.json()
            translated = "".join(
                part[0]
                for part in payload[0]
                if isinstance(part, list) and part and isinstance(part[0], str)
            )
        except (ValueError, TypeError, KeyError, IndexError):
            raise TranslationError("Google 翻译服务返回了无法识别的数据。") from None

        if not translated.strip():
            raise TranslationError("Google 翻译没有返回译文，请稍后再试。")
        detected = payload[2] if len(payload) > 2 and isinstance(payload[2], str) else source
        return TranslationResult(translated.strip(), "Google", detected)

    def _mymemory_translate(self, text: str, source: str, target: str) -> TranslationResult:
        if len(text) > 500:
            raise TranslationError("MyMemory 免费接口每次最多翻译 500 个字符，请切换 Google 或缩短文本。")
        actual_source = detect_language_heuristic(text) if source == "auto" else source
        if actual_source == "zh-TW":
            actual_source = "zh-CN"
        target_code = "zh-CN" if target == "zh-TW" else target
        params = {
            "q": text,
            "langpair": f"{actual_source}|{target_code}",
        }
        email = str(self.settings.get("mymemory_email", "")).strip()
        if email:
            params["de"] = email
        try:
            response = self.session.get(
                "https://api.mymemory.translated.net/get",
                params=params,
                timeout=(6, 25),
            )
        except requests.RequestException as exc:
            raise TranslationError(self._network_error(exc)) from None

        if response.status_code == 429:
            raise TranslationError("MyMemory 请求过于频繁，请稍后再试。")
        if response.status_code >= 400:
            raise TranslationError(f"MyMemory 翻译服务返回错误（HTTP {response.status_code}）。")
        try:
            payload = response.json()
            translated = payload["responseData"]["translatedText"]
            status = int(payload.get("responseStatus", 200))
        except (ValueError, TypeError, KeyError):
            raise TranslationError("MyMemory 翻译服务返回了无法识别的数据。") from None
        if status >= 400 or not isinstance(translated, str):
            message = payload.get("responseDetails") if isinstance(payload, dict) else None
            raise TranslationError(str(message or "MyMemory 翻译失败。"))
        translated = html.unescape(translated).strip()
        if not translated or re.search(r"MYMEMORY WARNING", translated, re.IGNORECASE):
            raise TranslationError("MyMemory 免费额度已用完，请稍后再试或切换引擎。")
        return TranslationResult(translated, "MyMemory", actual_source)

    def _chat_translate(
        self,
        text: str,
        source: str,
        target: str,
        provider: str,
        context: str = "",
    ) -> TranslationResult:
        if provider == "deepseek":
            api_key = reveal_secret(str(self.settings.get("deepseek_api_key", "")))
            base_url = str(
                self.settings.get("deepseek_base_url", "https://api.deepseek.com")
            ).strip().rstrip("/")
            model = str(self.settings.get("deepseek_model", "deepseek-chat")).strip()
            provider_label = "DeepSeek"
        else:
            api_key = reveal_secret(str(self.settings.get("openai_api_key", "")))
            base_url = str(self.settings.get("openai_base_url", "")).strip().rstrip("/")
            model = str(self.settings.get("openai_model", "")).strip()
            provider_label = "OpenAI 兼容接口"
        if not base_url or not model:
            raise TranslationError(f"请先在设置中填写 {provider_label} 的接口地址和模型名称。")
        if not api_key:
            raise TranslationError(f"请先在设置中填写 {provider_label} 的 API Key。")

        endpoint = base_url + "/chat/completions"
        source_name = (
            "自动检测"
            if source == "auto"
            else f"{get_language(source).label} ({source})"
        )
        target_name = f"{get_language(target).label} ({target})"
        system_prompt = (
            "You are a precise professional translation engine. "
            "Translate the user's text into the requested target language. "
            "Preserve meaning, tone, names, formatting and line breaks. "
            "Use the supplied nearby context only to resolve pronouns, terminology "
            "and implied meaning. Do not translate or repeat the context. "
            "Do not summarize, answer, explain, or add notes or quotation marks. "
            "Return only the translated text."
        )
        context_block = ""
        if context.strip():
            context_block = (
                "Nearby context (do not translate or repeat):\n"
                f"{context.strip()}\n\n"
            )
        user_prompt = (
            f"Source language: {source_name}\n"
            f"Target language: {target_name}\n\n"
            f"{context_block}"
            f"Text to translate:\n{text}"
        )
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": model,
            "temperature": 0.15,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        try:
            response = self.session.post(
                endpoint,
                headers=headers,
                json=body,
                timeout=(8, 60),
            )
        except requests.RequestException as exc:
            raise TranslationError(self._network_error(exc)) from None

        if response.status_code >= 400:
            detail = ""
            try:
                payload = response.json()
                detail = str(
                    payload.get("error", {}).get("message")
                    if isinstance(payload.get("error"), dict)
                    else payload.get("error", "")
                )
            except (ValueError, TypeError):
                detail = response.text[:180]
            suffix = f"：{detail}" if detail else ""
            raise TranslationError(
                f"{provider_label} 返回错误（HTTP {response.status_code}）{suffix}"
            )
        try:
            payload = response.json()
            translated = payload["choices"][0]["message"]["content"]
        except (ValueError, TypeError, KeyError, IndexError):
            raise TranslationError(f"{provider_label} 返回了无法识别的数据。") from None
        if not isinstance(translated, str) or not translated.strip():
            raise TranslationError("模型没有返回译文。")
        detected = detect_language_heuristic(text) if source == "auto" else source
        return TranslationResult(translated.strip(), provider_label, detected)

    @staticmethod
    def _network_error(exc: Exception) -> str:
        message = str(exc).lower()
        if any(marker in message for marker in _NETWORK_MARKERS):
            return "无法连接翻译服务，请检查网络、代理或防火墙设置。"
        return f"翻译请求失败：{exc}"

