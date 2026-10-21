"""System-audio loopback capture and streaming Vosk transcription."""

from __future__ import annotations

import json
import importlib.util
import os
import queue
import re
import threading
from collections import deque
from pathlib import Path
from difflib import SequenceMatcher

import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal

from .config import data_models_dir
from .languages import whisper_language


SAMPLE_RATE = 16000
WHISPER_MODEL_SPECS = (
    ("small", "ggml-small-q5_1.bin", 180_000_000),
    ("base", "ggml-base-q5_1.bin", 55_000_000),
)
ASR_FRAME_MS = 20
ASR_FRAME_SAMPLES = SAMPLE_RATE * ASR_FRAME_MS // 1000


def normalize_transcript(text: str) -> str:
    return re.sub(r"[\W_]+", "", text.lower())


def whisper_model_path() -> Path:
    directory = data_models_dir() / "whisper"
    for _, filename, minimum_size in WHISPER_MODEL_SPECS:
        path = directory / filename
        if path.exists() and path.stat().st_size >= minimum_size:
            return path
    return directory / WHISPER_MODEL_SPECS[-1][1]


def whisper_is_available() -> bool:
    path = whisper_model_path()
    return (
        importlib.util.find_spec("pywhispercpp") is not None
        and path.exists()
        and path.stat().st_size >= 55_000_000
    )


class PauseSegmenter:
    """Split streamed audio at natural pauses instead of fixed-time chunks."""

    def __init__(
        self,
        min_speech_ms: int = 320,
        end_silence_ms: int = 600,
        max_segment_ms: int = 10000,
        pre_roll_ms: int = 260,
        trailing_ms: int = 300,
    ):
        self.min_speech_frames = max(1, min_speech_ms // ASR_FRAME_MS)
        self.end_silence_frames = max(1, end_silence_ms // ASR_FRAME_MS)
        self.max_frames = max(1, max_segment_ms // ASR_FRAME_MS)
        self.trailing_frames = max(0, trailing_ms // ASR_FRAME_MS)
        self._pre_roll: deque[np.ndarray] = deque(
            maxlen=max(1, pre_roll_ms // ASR_FRAME_MS)
        )
        self._frames: list[np.ndarray] = []
        self._pending = np.empty(0, dtype=np.float32)
        self._in_speech = False
        self._speech_frames = 0
        self._last_speech_index = -1
        self._silence_frames = 0
        try:
            import webrtcvad

            self._vad = webrtcvad.Vad(2)
        except Exception:
            self._vad = None

    def add_block(self, samples: np.ndarray) -> np.ndarray | None:
        if samples.size == 0:
            return None
        self._pending = np.concatenate(
            (self._pending, np.asarray(samples, dtype=np.float32).reshape(-1))
        )
        completed: np.ndarray | None = None
        while self._pending.size >= ASR_FRAME_SAMPLES:
            frame = self._pending[:ASR_FRAME_SAMPLES].copy()
            self._pending = self._pending[ASR_FRAME_SAMPLES:]
            completed = self._add_frame(frame)
            if completed is not None:
                return completed
        return None

    def flush(self) -> np.ndarray | None:
        if not self._in_speech:
            self._reset()
            return None
        return self._finish_segment()

    def _add_frame(self, frame: np.ndarray) -> np.ndarray | None:
        pcm = (np.clip(frame, -1.0, 1.0) * 32767).astype(np.int16).tobytes()
        rms = float(np.sqrt(np.mean(np.square(frame)))) if frame.size else 0.0
        vad_active = False
        if self._vad is not None:
            try:
                vad_active = self._vad.is_speech(pcm, SAMPLE_RATE)
            except Exception:
                vad_active = False
        active = vad_active and rms > 0.00045

        if active:
            if not self._in_speech:
                self._in_speech = True
                self._frames = list(self._pre_roll)
                self._pre_roll.clear()
            self._frames.append(frame)
            self._speech_frames += 1
            self._last_speech_index = len(self._frames) - 1
            self._silence_frames = 0
        elif self._in_speech:
            self._frames.append(frame)
            self._silence_frames += 1
            if self._silence_frames >= self.end_silence_frames:
                return self._finish_segment()
        else:
            self._pre_roll.append(frame)

        if self._in_speech and len(self._frames) >= self.max_frames:
            return self._finish_segment()
        return None

    def _finish_segment(self) -> np.ndarray | None:
        if self._speech_frames < self.min_speech_frames or not self._frames:
            self._reset()
            return None
        end = min(
            len(self._frames),
            self._last_speech_index + 1 + self.trailing_frames,
        )
        audio = np.concatenate(self._frames[:end]).astype(np.float32)
        self._reset()
        return audio

    def _reset(self) -> None:
        self._frames = []
        self._in_speech = False
        self._speech_frames = 0
        self._last_speech_index = -1
        self._silence_frames = 0


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
            name="YuzhongChunshengWhisper",
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
        com_initialized = False
        try:
            import pythoncom
            import soundcard as sc

            # soundcard initializes COM only once at module import. Every new
            # capture thread therefore needs its own apartment initialization.
            pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
            com_initialized = True
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
        finally:
            if com_initialized:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

    def _transcribe_loop(self) -> None:
        if whisper_is_available():
            try:
                self._whisper_loop()
                return
            except Exception as exc:
                if self.language not in {"auto", "en"}:
                    if not self._stop_event.is_set():
                        self.error.emit(f"多语言语音识别失败：{exc}")
                    self._stop_event.set()
                    return
                self.status_changed.emit(
                    f"Whisper 不可用（{exc}），回退到 Vosk 英语模型…"
                )
        self._vosk_loop()

    def _vosk_loop(self) -> None:
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

    def _whisper_loop(self) -> None:
        from pywhispercpp.model import Model

        model_path = whisper_model_path()
        if not model_path.exists():
            raise RuntimeError(
                "Whisper 多语言模型尚未安装。请运行 "
                "python scripts/install_whisper_model.py"
            )
        self.status_changed.emit("正在加载 Whisper 多语言模型…")
        n_threads = max(4, (os.cpu_count() or 4) - 2)
        model = Model(
            str(model_path),
            n_threads=n_threads,
            print_progress=False,
            print_realtime=False,
            print_timestamps=False,
            suppress_non_speech_tokens=True,
            redirect_whispercpp_logs_to=False,
        )
        model_label = "small" if "small" in model_path.name else "base"
        self.device_label = f"Whisper {model_label} · 多语言"
        if not self._stop_event.is_set():
            self.status_changed.emit(
                "Whisper 多语言已就绪 · 正在聆听电脑播放的声音…"
            )
        language = whisper_language(self.language)
        auto_detect = not language
        detected_language = language
        if language:
            available_languages = set(Model.available_languages())
            if language not in available_languages:
                self.status_changed.emit(
                    "所选源语言不在 Whisper 模型支持范围内，改为自动识别…"
                )
                language = ""
                detected_language = ""
                auto_detect = True
        asr_prompt = ""
        segmenter = PauseSegmenter()
        while not self._stop_event.is_set():
            try:
                item = self._audio_queue.get(timeout=0.3)
            except queue.Empty:
                continue
            if item is None:
                break
            if item.size == 0:
                continue
            chunk = segmenter.add_block(item)
            if chunk is not None:
                detected_language, asr_prompt = self._transcribe_whisper_segment(
                    model,
                    chunk,
                    auto_detect,
                    detected_language,
                    asr_prompt,
                )
        final_chunk = segmenter.flush()
        if final_chunk is not None and not self._stop_event.is_set():
            self._transcribe_whisper_segment(
                model,
                final_chunk,
                auto_detect,
                detected_language,
                asr_prompt,
            )

    def _transcribe_whisper_segment(
        self,
        model,
        chunk: np.ndarray,
        auto_detect: bool,
        detected_language: str,
        asr_prompt: str,
    ) -> tuple[str, str]:
        rms = float(np.sqrt(np.mean(np.square(chunk))))
        if rms < 0.00035:
            return detected_language, asr_prompt
        peak = float(np.max(np.abs(chunk)))
        chunk = np.clip(chunk / max(peak, 0.04) * 0.78, -1.0, 1.0)
        previous_language = detected_language
        if auto_detect:
            detection = model.auto_detect_language(chunk.astype(np.float32))
            new_language, probability = detection[0]
            if new_language and (
                float(probability) >= 0.55 or not detected_language
            ):
                detected_language = new_language
            if not detected_language:
                return "", asr_prompt
        if previous_language and previous_language != detected_language:
            asr_prompt = ""
        transcribe_options = {
            "language": detected_language,
            "detect_language": False,
            "no_context": False,
            "no_timestamps": False,
            "print_progress": False,
            "print_realtime": False,
            "print_timestamps": False,
            "suppress_blank": True,
            "suppress_non_speech_tokens": True,
            "no_speech_thold": 0.68,
            "logprob_thold": -1.5,
            "temperature": 0.0,
            "greedy": {"best_of": 3},
        }
        if asr_prompt:
            transcribe_options["initial_prompt"] = asr_prompt
        segments = model.transcribe(
            chunk.astype(np.float32),
            **transcribe_options,
        )
        text = " ".join(
            segment.text.strip()
            for segment in segments
            if segment.text and segment.text.strip()
        )
        self._emit_text(text, detected_language)
        if text:
            asr_prompt = (asr_prompt + " " + text).strip()[-220:]
        return detected_language, asr_prompt

    def _emit_text(self, text: str, language_code: str | None = None) -> None:
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
            and SequenceMatcher(None, key, self._last_transcript_key).ratio() > 0.985
        ):
            return
        self._last_transcript_key = key
        self.transcript_ready.emit(text, language_code or self.language)

