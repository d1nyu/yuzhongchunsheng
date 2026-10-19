"""Local settings and application paths."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


APP_NAME = "羽中纯声"
# Internal identifier kept stable so existing encrypted settings remain readable.
APP_ID = "YiSheng"
PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_SETTINGS: dict[str, Any] = {
    "engine": "deepseek",
    "source_lang": "auto",
    "target_lang": "zh-CN",
    "speech_lang": "zh-CN",
    "auto_translate": False,
    "auto_speak": True,
    "last_mode": "text",
    "deepseek_base_url": "https://api.deepseek.com",
    "deepseek_model": "deepseek-chat",
    "deepseek_api_key": "",
    "openai_base_url": "https://api.openai.com/v1",
    "openai_model": "gpt-4o-mini",
    "openai_api_key": "",
    "mymemory_email": "",
    "video_region": [],
    "audio_source_mode": "audio",
    "overlay_enabled": True,
    "overlay_pos": [],
    "geometry": "",
}


ENGINE_LABELS: dict[str, str] = {
    "deepseek": "DeepSeek",
    "google": "Google 免费",
    "mymemory": "MyMemory 免费",
    "openai": "OpenAI 兼容接口",
}


def config_dir() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / APP_ID
    return Path.home() / ".config" / APP_ID


def config_path() -> Path:
    return config_dir() / "settings.json"


def log_path() -> Path:
    return config_dir() / "error.log"


def data_models_dir() -> Path:
    base = os.environ.get("PROGRAMDATA") or os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / APP_ID / "models"
    return Path.home() / ".local" / "share" / APP_ID / "models"


def load_settings() -> dict[str, Any]:
    settings = dict(DEFAULT_SETTINGS)
    path = config_path()
    try:
        if path.exists():
            loaded = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(loaded, dict):
                settings.update(loaded)
    except (OSError, ValueError, TypeError):
        pass
    return settings


def save_settings(settings: dict[str, Any]) -> None:
    directory = config_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = config_path()
    temporary = path.with_suffix(".tmp")
    payload = json.dumps(settings, ensure_ascii=False, indent=2)
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)


def resource_path(*parts: str) -> Path:
    return PROJECT_ROOT.joinpath(*parts)

