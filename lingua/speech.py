"""Windows speech recognition and text-to-speech integration."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import gc
from pathlib import Path
from typing import Any

from PyQt5.QtCore import QObject, QThread, pyqtSignal

from .config import resource_path
from .languages import language_label, sapi_lcid


CREATE_NO_WINDOW = 0x08000000


def _powershell_path() -> Path:
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    bundled = system_root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    if bundled.exists():
        return bundled
    for name in ("powershell", "pwsh"):
        found = shutil.which(name)
        if found:
            return Path(found)
    raise RuntimeError("找不到 PowerShell，无法启动 Windows 语音功能。")


def _hidden_process_kwargs() -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "creationflags": CREATE_NO_WINDOW,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = startupinfo
    return kwargs


def _read_json_result(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError):
        return {}


def list_installed_recognizers(timeout: float = 8.0) -> list[dict[str, str]]:
    """Return installed Windows speech recognizers as dictionaries."""
    handle, raw_path = tempfile.mkstemp(
        prefix="yuzhongchunsheng-recognizers-", suffix=".json"
    )
    os.close(handle)
    output_path = Path(raw_path)
    try:
        command = [
            str(_powershell_path()),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(resource_path("scripts", "list_recognizers.ps1")),
            "-OutputFile",
            str(output_path),
        ]
        subprocess.run(
            command,
            timeout=timeout,
            check=False,
            **_hidden_process_kwargs(),
        )
        payload = _read_json_result(output_path)
        items = payload.get("recognizers", [])
        if payload.get("ok") and isinstance(items, list):
            result = []
            for item in items:
                if isinstance(item, dict) and item.get("culture"):
                    result.append(
                        {
                            "culture": str(item.get("culture", "")),
                            "name": str(item.get("name", "")),
                            "description": str(item.get("description", "")),
                        }
                    )
            return result
        return []
    except (OSError, subprocess.SubprocessError, RuntimeError):
        return []
    finally:
        try:
            output_path.unlink()
        except OSError:
            pass


def list_sapi_voices() -> list[dict[str, Any]]:
    """Inspect installed SAPI voices without blocking the GUI startup."""
    result: list[dict[str, Any]] = []
    try:
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        voice = None
        tokens = []
        try:
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            tokens = list(voice.GetVoices())
            for token in tokens:
                try:
                    lcid = int(str(token.GetAttribute("Language")), 16)
                except (TypeError, ValueError):
                    lcid = 0
                result.append(
                    {
                        "description": str(token.GetDescription()),
                        "language": lcid,
                    }
                )
        finally:
            tokens = []
            voice = None
            gc.collect()
            pythoncom.CoUninitialize()
    except Exception:
        return []
    return result


def _friendly_speech_error(message: str) -> str:
    lowered = message.lower()
    if "no_default_audio" in lowered or "no audio" in lowered or "audio device" in lowered:
        return "没有找到可用的麦克风，请检查 Windows 输入设备设置。"
    if "permission" in lowered or "access" in lowered:
        return "无法访问麦克风。请在 Windows 设置中允许桌面应用使用麦克风。"
    if "not installed" in lowered or "未安装" in message:
        return message
    if message == "NO_SPEECH":
        return "没有识别到语音，请靠近麦克风再试一次。"
    return f"语音识别失败：{message}"


class RecognitionWorker(QThread):
    recognized = pyqtSignal(str, str, float)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, culture: str, timeout_seconds: int = 20, parent: QObject | None = None):
        super().__init__(parent)
        self.culture = culture
        self.timeout_seconds = timeout_seconds
        self._process: subprocess.Popen[bytes] | None = None
        self._cancel_requested = False

    def run(self) -> None:
        handle, raw_path = tempfile.mkstemp(
            prefix="yuzhongchunsheng-speech-", suffix=".json"
        )
        os.close(handle)
        output_path = Path(raw_path)
        try:
            command = [
                str(_powershell_path()),
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(resource_path("scripts", "recognize_once.ps1")),
                "-Culture",
                self.culture,
                "-TimeoutSeconds",
                str(self.timeout_seconds),
                "-OutputFile",
                str(output_path),
            ]
            self._process = subprocess.Popen(command, **_hidden_process_kwargs())
            try:
                self._process.wait(timeout=self.timeout_seconds + 10)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=3)
                if not self._cancel_requested:
                    self.failed.emit("语音识别超时，请重试。")
                return

            if self._cancel_requested:
                self.cancelled.emit()
                return

            payload = _read_json_result(output_path)
            if not payload:
                self.failed.emit("语音识别进程没有返回结果，请重试。")
                return
            if not payload.get("ok"):
                self.failed.emit(_friendly_speech_error(str(payload.get("error", ""))))
                return
            text = str(payload.get("text", "")).strip()
            if not text:
                self.failed.emit(_friendly_speech_error("NO_SPEECH"))
                return
            confidence = float(payload.get("confidence", 0.0))
            self.recognized.emit(text, self.culture, confidence)
        except Exception as exc:
            if self._cancel_requested:
                self.cancelled.emit()
            else:
                self.failed.emit(_friendly_speech_error(str(exc)))
        finally:
            self._process = None
            try:
                output_path.unlink()
            except OSError:
                pass

    def cancel(self) -> None:
        self._cancel_requested = True
        process = self._process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass


class WindowsSpeaker(QObject):
    speaking_changed = pyqtSignal(bool)
    error = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._state_lock = threading.Lock()

    def speak(self, text: str, language_code: str) -> bool:
        text = text.strip()
        if not text:
            return False
        self.stop()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._speak_worker,
            args=(text, language_code, self._stop_event),
            daemon=True,
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=0.35)

    def _speak_worker(self, text: str, language_code: str, stop_event: threading.Event) -> None:
        voice = None
        try:
            import pythoncom
            import win32com.client

            pythoncom.CoInitialize()
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            target_lcid = sapi_lcid(language_code)
            selected = None
            for token in voice.GetVoices():
                try:
                    token_lcid = int(str(token.GetAttribute("Language")), 16)
                except (TypeError, ValueError):
                    continue
                if target_lcid is not None and token_lcid == target_lcid:
                    selected = token
                    break
            if selected is None:
                label = language_label(language_code)
                self.error.emit(
                    f"Windows 中没有可朗读{label}的语音包。"
                    "请在“设置 → 时间和语言 → 语音”中安装对应语音。"
                )
                return

            voice.Voice = selected
            voice.Rate = 0
            self.speaking_changed.emit(True)
            voice.Speak(text, 1)
            started = False
            deadline = time.monotonic() + 5.0
            while not stop_event.is_set():
                try:
                    state = int(voice.Status.RunningState)
                except Exception:
                    break
                if state == 2:
                    started = True
                if state == 1 and started:
                    break
                if not started and time.monotonic() > deadline:
                    break
                time.sleep(0.08)
            if stop_event.is_set():
                try:
                    voice.Speak("", 2)
                except Exception:
                    pass
        except Exception as exc:
            message = str(exc)
            if "No voice installed" in message or "voice" in message.lower():
                self.error.emit("本机没有可用的语音输出设备或语音包。")
            else:
                self.error.emit(f"朗读失败：{message}")
        finally:
            try:
                import pythoncom

                pythoncom.CoUninitialize()
            except Exception:
                pass
            with self._state_lock:
                if self._thread is threading.current_thread():
                    self._thread = None
            self.speaking_changed.emit(False)

