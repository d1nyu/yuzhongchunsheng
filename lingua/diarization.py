"""Local speaker diarization and music/speech content classification."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .config import data_models_dir


SAMPLE_RATE = 16000


def diarization_model_paths() -> tuple[Path, Path]:
    directory = data_models_dir() / "diarization"
    return (
        directory / "segmentation.onnx",
        directory / "speaker_embedding.onnx",
    )


def diarization_is_available() -> bool:
    segmentation, embedding = diarization_model_paths()
    return (
        segmentation.exists()
        and segmentation.stat().st_size > 1_000_000
        and embedding.exists()
        and embedding.stat().st_size > 20_000_000
    )


def audio_tagging_model_paths() -> tuple[Path, Path]:
    directory = data_models_dir() / "audio_tagging"
    return (
        directory / "model.int8.onnx",
        directory / "class_labels_indices.csv",
    )


def audio_tagging_is_available() -> bool:
    model, labels = audio_tagging_model_paths()
    return (
        model.exists()
        and model.stat().st_size > 5_000_000
        and labels.exists()
    )


@dataclass
class SpeakerSegment:
    speaker: str
    audio: np.ndarray
    start: float
    end: float
    overlap: bool = False


class SpeakerDiarizer:
    """Diarize each utterance and keep speaker IDs stable across a session."""

    def __init__(self, similarity_threshold: float = 0.55):
        import sherpa_onnx

        segmentation_model, embedding_model = diarization_model_paths()
        config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
            segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
                pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                    model=str(segmentation_model),
                    window_shift_ratio=0.1,
                )
            ),
            embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(
                model=str(embedding_model)
            ),
            clustering=sherpa_onnx.FastClusteringConfig(
                num_clusters=-1,
                threshold=0.5,
            ),
            min_duration_on=0.25,
            min_duration_off=0.35,
        )
        if not config.validate():
            raise RuntimeError("说话人分离模型文件不完整。")
        self._diarizer = sherpa_onnx.OfflineSpeakerDiarization(config)
        extractor_config = sherpa_onnx.SpeakerEmbeddingExtractorConfig(
            model=str(embedding_model),
            num_threads=max(2, (os.cpu_count() or 4) // 2),
        )
        self._extractor = sherpa_onnx.SpeakerEmbeddingExtractor(extractor_config)
        self._similarity_threshold = similarity_threshold
        self._prototypes: list[np.ndarray] = []
        self._last_speaker = ""

    @property
    def speaker_count(self) -> int:
        return len(self._prototypes)

    def segment(self, audio: np.ndarray) -> list[SpeakerSegment]:
        audio = np.ascontiguousarray(audio, dtype=np.float32).reshape(-1)
        if audio.size < int(SAMPLE_RATE * 0.4):
            speaker = self._assign(audio)
            if not speaker:
                return []
            return [
                SpeakerSegment(
                    speaker=speaker,
                    audio=audio,
                    start=0.0,
                    end=audio.size / SAMPLE_RATE,
                )
            ]
        try:
            result = self._diarizer.process(audio).sort_by_start_time()
        except Exception:
            speaker = self._assign(audio)
            if not speaker:
                return []
            return [
                SpeakerSegment(
                    speaker=speaker,
                    audio=audio,
                    start=0.0,
                    end=audio.size / SAMPLE_RATE,
                )
            ]

        pieces = []
        for item in result:
            start = max(0, int(float(item.start) * SAMPLE_RATE))
            end = min(audio.size, int(float(item.end) * SAMPLE_RATE))
            if end - start < int(SAMPLE_RATE * 0.2):
                continue
            pieces.append((start, end, int(item.speaker)))
        if not pieces:
            speaker = self._assign(audio)
            if not speaker:
                return []
            return [
                SpeakerSegment(
                    speaker=speaker,
                    audio=audio,
                    start=0.0,
                    end=audio.size / SAMPLE_RATE,
                )
            ]

        segments: list[SpeakerSegment] = []
        for index, (start, end, local_speaker) in enumerate(pieces):
            slice_audio = audio[start:end]
            speaker = self._assign(slice_audio)
            if not speaker:
                continue
            overlap = False
            for other_index, (other_start, other_end, other_speaker) in enumerate(pieces):
                if other_index == index or other_speaker == local_speaker:
                    continue
                overlap_seconds = min(end, other_end) - max(start, other_start)
                if overlap_seconds > int(SAMPLE_RATE * 0.12):
                    overlap = True
                    break
            segments.append(
                SpeakerSegment(
                    speaker=speaker,
                    audio=slice_audio,
                    start=start / SAMPLE_RATE,
                    end=end / SAMPLE_RATE,
                    overlap=overlap,
                )
            )
        return segments

    def _assign(self, audio: np.ndarray) -> str:
        embedding = self._compute_embedding(audio)
        if embedding is None:
            return self._last_speaker
        if not self._prototypes:
            self._prototypes.append(embedding.copy())
            self._last_speaker = "说话人 1"
            return self._last_speaker
        similarities = [float(np.dot(embedding, proto)) for proto in self._prototypes]
        best_index = int(np.argmax(similarities))
        if similarities[best_index] >= self._similarity_threshold:
            old = self._prototypes[best_index]
            updated = old * 0.85 + embedding * 0.15
            self._prototypes[best_index] = updated / np.linalg.norm(updated)
            self._last_speaker = f"说话人 {best_index + 1}"
            return self._last_speaker
        if len(self._prototypes) >= 8:
            self._last_speaker = f"说话人 {best_index + 1}"
            return self._last_speaker
        self._prototypes.append(embedding.copy())
        self._last_speaker = f"说话人 {len(self._prototypes)}"
        return self._last_speaker

    def _compute_embedding(self, audio: np.ndarray) -> np.ndarray | None:
        audio = np.ascontiguousarray(audio, dtype=np.float32).reshape(-1)
        minimum = int(SAMPLE_RATE * 0.4)
        if audio.size < minimum:
            audio = np.pad(audio, (0, minimum - audio.size))
        try:
            stream = self._extractor.create_stream()
            stream.accept_waveform(SAMPLE_RATE, audio)
            stream.input_finished()
            if not self._extractor.is_ready(stream):
                return None
            vector = np.asarray(self._extractor.compute(stream), dtype=np.float32)
            norm = float(np.linalg.norm(vector))
            if norm <= 1e-6:
                return None
            return vector / norm
        except Exception:
            return None


@dataclass
class AudioContent:
    music_only: bool
    music_overlap: bool
    speech_probability: float
    music_probability: float


class AudioContentGate:
    """Recognize speech versus music/lyrics before ASR."""

    _SPEECH_TAGS = (
        "Speech",
        "Speech synthesizer",
        "Conversation",
        "Narration, monologue",
        "Male speech",
        "Female speech",
        "Child speech",
    )
    _MUSIC_TAGS = (
        "Music",
        "Singing",
        "Vocal music",
        "A capella",
        "Choir",
        "Song",
        "Male singing",
        "Female singing",
    )

    def __init__(self):
        import sherpa_onnx

        model, labels = audio_tagging_model_paths()
        config = sherpa_onnx.AudioTaggingConfig(
            model=sherpa_onnx.AudioTaggingModelConfig(
                ced=str(model),
                num_threads=2,
                provider="cpu",
            ),
            labels=str(labels),
            top_k=12,
        )
        if not config.validate():
            raise RuntimeError("音乐/语音分类模型文件不完整。")
        self._tagger = sherpa_onnx.AudioTagging(config)

    def classify(self, audio: np.ndarray) -> AudioContent:
        try:
            stream = self._tagger.create_stream()
            stream.accept_waveform(
                SAMPLE_RATE,
                np.ascontiguousarray(audio, dtype=np.float32).reshape(-1),
            )
            events = self._tagger.compute(stream)
            probabilities: dict[str, float] = {
                str(event.name): float(event.prob) for event in events
            }
            speech = max(
                (
                    value
                    for name, value in probabilities.items()
                    if any(name.startswith(tag) for tag in self._SPEECH_TAGS)
                ),
                default=0.0,
            )
            music = max(
                (
                    value
                    for name, value in probabilities.items()
                    if any(name.startswith(tag) for tag in self._MUSIC_TAGS)
                ),
                default=0.0,
            )
            music_only = speech < 0.25 and music >= 0.3 and music > speech * 1.35
            music_overlap = not music_only and speech >= 0.22 and music >= 0.18
            return AudioContent(music_only, music_overlap, speech, music)
        except Exception:
            return AudioContent(False, False, 0.0, 0.0)

