"""System-audio loopback capture and streaming Vosk transcription."""

from __future__ import annotations

import json
import queue
import re
import threading
from difflib import SequenceMatcher

import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal

from .config import data_models_dir


SAMPLE_RATE = 16000


def normalize_transcript(text: str) -> str:
    return re.sub(r"[\W_]+", "", text.lower())


class SystemAudioTranscriber(QObject):
    transcript_ready = pyqtSignal(str, str)
    status_changed = pyqtSignal(str)
    level_changed = pyqtSignal(float)
    error = pyqtSignal(str)

    def __init__(self, language: str = "en", parent: QObject | None = None):
        super().__init__(parent)
        self.language = language
        self._stop_event = threading.Event()
        self._audio_queue: queue.Queue[np.ndarray | None] = queue.Queue(maxsize=80)
        self._capture_thread: threading.Thread | None = None
        self._infer_thread: threading.Thread | None = None
        self._last_transcript_key = ""
        self.speaker_name = ""
        self.device_label = ""

    def start(self) -> None:
        if self._capture_thread is not None and self._capture_thread.is_alive():
            return
        self._stop_event.clear()
        self._last_transcript_key = ""
        self._audio_queue = queue.Queue(maxsize=80)
        self._capture_thread = threading.Thread(
            target=self._capture_loop,
            name="YuzhongChunshengAudioCapture",
            daemon=True,
        )
        self._infer_thread = threading.Thread(
            target=self._transcribe_loop,
            name="YuzhongChunshengVosk",
            daemon=True,
        )
        self._capture_thread.start()
        self._infer_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        try:
            self._audio_queue.put_nowait(None)
        except queue.Full:
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._audio_queue.put_nowait(None)
            except queue.Full:
                pass
        for thread in (self._capture_thread, self._infer_thread):
            if thread is not None and thread.is_alive():
                thread.join(timeout=2.5)

    def _capture_loop(self) -> None:
        try:
            import soundcard as sc

            speaker = sc.default_speaker()
            if speaker is None:
                raise RuntimeError("没有找到默认扬声器。")
            self.speaker_name = speaker.name
            loopback = sc.get_microphone(id=speaker.name, include_loopback=True)
            if loopback is None:
                raise RuntimeError("默认扬声器不支持声音回环采集。")
            self.status_changed.emit(f"正在连接电脑声音 · {speaker.name}")
            block_frames = int(SAMPLE_RATE * 0.2)
            with loopback.recorder(samplerate=SAMPLE_RATE, channels=1) as recorder:
                self.status_changed.emit("正在聆听电脑播放的声音…")
                while not self._stop_event.is_set():
                    data = recorder.record(numframes=block_frames)
                    if data is None or len(data) == 0:
                        continue
                    mono = np.asarray(data, dtype=np.float32)
                    if mono.ndim > 1:
                        mono = mono.mean(axis=1)
                    mono = mono.reshape(-1)
                    rms = float(np.sqrt(np.mean(np.square(mono)))) if mono.size else 0.0
                    self.level_changed.emit(min(1.0, rms * 28.0))
                    try:
                        self._audio_queue.put_nowait(mono.copy())
                    except queue.Full:
                        try:
                            self._audio_queue.get_nowait()
                        except queue.Empty:
                            pass
                        try:
                            self._audio_queue.put_nowait(mono.copy())
                        except queue.Full:
                            pass
        except Exception as exc:
            if not self._stop_event.is_set():
                self.error.emit(f"无法采集电脑声音：{exc}")
            self._stop_event.set()
            try:
                self._audio_queue.put_nowait(None)
            except queue.Full:
                pass

    def _transcribe_loop(self) -> None:
        recognizer = None
        try:
            import vosk

            vosk.SetLogLevel(-1)
            model_path = data_models_dir() / "vosk" / "vosk-model-small-en-us-0.15"
            if not model_path.exists():
                raise RuntimeError(
                    "英文语音模型尚未安装。请运行 "
                    "python scripts/install_vosk_model.py"
                )
            self.status_changed.emit("正在加载本地 Vosk 语音模型…")
            model = vosk.Model(str(model_path))
            recognizer = vosk.KaldiRecognizer(model, SAMPLE_RATE)
            self.device_label = "Vosk English"
            if not self._stop_event.is_set():
                self.status_changed.emit("Vosk 已就绪 · 正在聆听电脑播放的声音…")
            while not self._stop_event.is_set():
                try:
                    item = self._audio_queue.get(timeout=0.3)
                except queue.Empty:
                    continue
                if item is None:
                    break
                if item.size == 0:
                    continue
                rms = float(np.sqrt(np.mean(np.square(item))))
                if rms < 0.0003:
                    pcm = np.zeros(item.size, dtype=np.int16).tobytes()
                else:
                    peak = float(np.max(np.abs(item)))
                    scaled = item / max(peak, 0.04) * 0.72
                    pcm = (np.clip(scaled, -1.0, 1.0) * 32767).astype(np.int16).tobytes()
                if recognizer.AcceptWaveform(pcm):
                    result = json.loads(recognizer.Result())
                    text = str(result.get("text", "")).strip()
                    self._emit_text(text)
        except Exception as exc:
            if not self._stop_event.is_set():
                self.error.emit(f"本地语音转写失败：{exc}")
            self._stop_event.set()
        finally:
            if recognizer is not None:
                try:
                    result = json.loads(recognizer.FinalResult())
                    self._emit_text(str(result.get("text", "")).strip())
                except Exception:
                    pass

    def _emit_text(self, text: str) -> None:
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return
        lowered = text.lower()
        if any(
            phrase in lowered
            for phrase in (
                "thanks for watching",
                "thank you for watching",
                "please subscribe",
                "subscribe to my channel",
            )
        ):
            return
        key = normalize_transcript(text)
        if not key:
            return
        if (
            self._last_transcript_key
            and SequenceMatcher(None, key, self._last_transcript_key).ratio() > 0.92
        ):
            return
        self._last_transcript_key = key
        self.transcript_ready.emit(text, self.language)

