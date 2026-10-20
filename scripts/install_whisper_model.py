"""Download the multilingual Whisper model used for system-audio translation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lingua.audio_translate import whisper_model_path


URLS = (
    "https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/"
    "ggml-base-q5_1.bin",
    "https://github.com/Vaselevs/asr-models-mirror/releases/download/"
    "models-v1/ggml-base-q8_0.bin",
)


def download(url: str, target: Path) -> None:
    response = requests.get(url, timeout=(20, 300), stream=True)
    response.raise_for_status()
    total = int(response.headers.get("content-length", 0))
    received = 0
    temporary = target.with_suffix(target.suffix + ".part")
    with temporary.open("wb") as handle:
        for block in response.iter_content(1024 * 256):
            if not block:
                continue
            handle.write(block)
            received += len(block)
            if total:
                print(
                    f"\r{received / total:6.1%}  "
                    f"{received / 1048576:.1f}/{total / 1048576:.1f} MB",
                    end="",
                    flush=True,
                )
    print()
    temporary.replace(target)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    target = whisper_model_path()
    if target.exists() and target.stat().st_size > 50 * 1024 * 1024 and not args.force:
        print(f"Model already installed: {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for url in URLS:
        try:
            print(f"Downloading {url}")
            download(url, target)
            if target.stat().st_size < 50 * 1024 * 1024:
                target.unlink(missing_ok=True)
                raise RuntimeError("Downloaded model is unexpectedly small.")
            print(f"Installed: {target}")
            return
        except Exception as exc:
            last_error = exc
            print(f"Failed: {exc}")
    raise SystemExit(f"Could not install the Whisper model: {last_error}")


if __name__ == "__main__":
    main()

