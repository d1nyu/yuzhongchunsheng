"""Global Windows hotkey registration without extra dependencies."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from PyQt5.QtCore import (
    QAbstractNativeEventFilter,
    QCoreApplication,
    QObject,
    pyqtSignal,
)


WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000


class _NativeHotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, owner: "GlobalHotkeyFilter"):
        super().__init__()
        self.owner = owner

    def nativeEventFilter(self, event_type, message):  # type: ignore[no-untyped-def]
        if str(event_type) not in (
            "windows_generic_MSG",
            "windows_dispatcher_MSG",
            "b'windows_generic_MSG'",
            "b'windows_dispatcher_MSG'",
        ):
            return False, 0
        try:
            msg = wintypes.MSG.from_address(int(message))
        except (TypeError, ValueError):
            return False, 0
        if msg.message == WM_HOTKEY and int(msg.wParam) == self.owner.hotkey_id:
            self.owner.triggered.emit()
            return True, 0
        return False, 0


class GlobalHotkeyFilter(QObject):
    triggered = pyqtSignal()

    def __init__(
        self,
        modifiers: int = MOD_CONTROL | MOD_ALT,
        virtual_key: int = ord("T"),
        hotkey_id: int = 0xB001,
        parent=None,
    ):
        super().__init__(parent)
        self.modifiers = modifiers | MOD_NOREPEAT
        self.virtual_key = virtual_key
        self.hotkey_id = hotkey_id
        self.registered = False
        self._native_filter = _NativeHotkeyFilter(self)

    def register(self) -> bool:
        if self.registered:
            return True
        try:
            self.registered = bool(
                ctypes.windll.user32.RegisterHotKey(
                    None,
                    self.hotkey_id,
                    self.modifiers,
                    self.virtual_key,
                )
            )
        except Exception:
            self.registered = False
        if self.registered:
            QCoreApplication.instance().installNativeEventFilter(self._native_filter)
        return self.registered

    def unregister(self) -> None:
        if not self.registered:
            return
        try:
            ctypes.windll.user32.UnregisterHotKey(None, self.hotkey_id)
        except Exception:
            pass
        app = QCoreApplication.instance()
        if app is not None:
            app.removeNativeEventFilter(self._native_filter)
        self.registered = False

