"""Download local speaker diarization and audio-tagging models."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lingua.config import data_models_dir


FILES = (
    (
        "diarization/segmentation.onnx",
        "https://hf-mirror.com/csukuangfj/"
        "sherpa-onnx-pyannote-segmentation-3-0/resolve/main/model.onnx",
        5_000_000,
    ),
    (
        "diarization/speaker_embedding.onnx",
        "https://hf-mirror.com/echo-hello/"
        "speech_campplus_sv_zh_en_16k-common_advanced-onnx/resolve/main/"
        "onnx/speech_campplus_sv_zh_en_16k-common_advanced.onnx",
        20_000_000,
    ),
    (
        "audio_tagging/model.int8.onnx",
        "https://hf-mirror.com/k2-fsa/"
        "sherpa-onnx-ced-tiny-audio-tagging-2024-04-19/resolve/main/"
        "model.int8.onnx",
        5_000_000,
    ),
    (
        "audio_tagging/class_labels_indices.csv",
        "https://hf-mirror.com/k2-fsa/"
        "sherpa-onnx-ced-tiny-audio-tagging-2024-04-19/resolve/main/"
        "class_labels_indices.csv",
        1_000,
    ),
)


def download(url: str, target: Path) -> None:
    response = requests.get(url, timeout=(20, 180), stream=True)
    response.raise_for_status()
    temporary = target.with_suffix(target.suffix + ".part")
    with temporary.open("wb") as handle:
        for block in response.iter_content(256 * 1024):
            if block:
                handle.write(block)
    temporary.replace(target)
    print(f"Installed: {target}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    root = data_models_dir()
    for relative, url, minimum_size in FILES:
        target = root / relative
        if target.exists() and target.stat().st_size >= minimum_size and not args.force:
            print(f"Already installed: {target}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {url}")
        download(url, target)
        if target.stat().st_size < minimum_size:
            target.unlink(missing_ok=True)
            raise SystemExit(f"Downloaded file is incomplete: {target}")


if __name__ == "__main__":
    main()

