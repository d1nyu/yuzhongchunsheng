"""Download and install the offline English Vosk model used by video audio mode."""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lingua.config import data_models_dir


MODEL_FOLDER = "vosk-model-small-en-us-0.15"
URLS = (
    "https://hf-mirror.com/ambind/vosk-model-small-en-us-0.15/"
    "resolve/main/vosk-model-small-en-us-0.15_c_.zip",
    "https://github.com/Vaselevs/asr-models-mirror/releases/download/"
    "models-v1/vosk-model-small-en-us-0.15.zip",
)


def download(url: str, target: Path) -> None:
    response = requests.get(url, timeout=(20, 180), stream=True)
    response.raise_for_status()
    total = int(response.headers.get("content-length", 0))
    received = 0
    with target.open("wb") as handle:
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    model_dir = data_models_dir() / "vosk"
    target = model_dir / MODEL_FOLDER
    if target.exists() and (target / "am" / "final.mdl").exists() and not args.force:
        print(f"Model already installed: {target}")
        return

    model_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="yuzhongchunsheng-vosk-") as temporary:
        temporary_path = Path(temporary)
        archive = temporary_path / "model.zip"
        last_error: Exception | None = None
        for url in URLS:
            try:
                print(f"Downloading {url}")
                download(url, archive)
                with zipfile.ZipFile(archive) as package:
                    package.extractall(temporary_path / "unpacked")
                extracted = temporary_path / "unpacked" / MODEL_FOLDER
                if not (extracted / "am" / "final.mdl").exists():
                    raise RuntimeError("Downloaded archive does not contain the expected model.")
                if target.exists():
                    shutil.rmtree(target)
                shutil.move(str(extracted), str(target))
                print(f"Installed: {target}")
                return
            except Exception as exc:
                last_error = exc
                print(f"Failed: {exc}")
        raise SystemExit(f"Could not install the model: {last_error}")


if __name__ == "__main__":
    main()

