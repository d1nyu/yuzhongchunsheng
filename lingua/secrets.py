"""Protect locally stored API keys with Windows DPAPI when available."""

from __future__ import annotations

import base64
import os


_PREFIX = "dpapi:"


def protect_secret(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if os.name != "nt":
        return value
    try:
        import win32crypt

        entropy = b"YiSheng-local-api-key-v1"
        encrypted = win32crypt.CryptProtectData(
            value.encode("utf-8"),
            "YiSheng API key",
            entropy,
            None,
            None,
            0x1,
        )
        return _PREFIX + base64.b64encode(encrypted).decode("ascii")
    except Exception:
        return value


def reveal_secret(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if not value.startswith(_PREFIX):
        return value
    try:
        import win32crypt

        encrypted = base64.b64decode(value[len(_PREFIX) :])
        entropy = b"YiSheng-local-api-key-v1"
        _, decrypted = win32crypt.CryptUnprotectData(
            encrypted,
            entropy,
            None,
            None,
            0x1,
        )
        return decrypted.decode("utf-8")
    except Exception:
        return ""

