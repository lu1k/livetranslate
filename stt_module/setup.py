"""
setup.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
One-time setup script:
  1. Verify Python version.
  2. Check / install pip packages.
  3. Download Silero VAD model (torch.hub cache).
  4. Download MediaPipe hand_landmarker.task.
  5. Warm-start faster-whisper (downloads model weights).
  6. Print system capability summary.

Run once before main.py:
    python setup.py
    python setup.py --model small   # if you want the small model
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

# ──────────────────────────────────────────────────────────────
MIN_PYTHON = (3, 9)

def check_python():
    v = sys.version_info[:2]
    if v < MIN_PYTHON:
        sys.exit(f"❌  Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ required. Got {v[0]}.{v[1]}")
    print(f"✓  Python {v[0]}.{v[1]}")


# ──────────────────────────────────────────────────────────────
def check_packages():
    """Attempt to import every required package; install missing ones."""
    required = {
        "sounddevice"    : "sounddevice",
        "numpy"          : "numpy",
        "torch"          : "torch",
        "faster_whisper" : "faster-whisper",
        "cv2"            : "opencv-python",
        "mediapipe"      : "mediapipe",
        "PIL"            : "Pillow",
        "deep_translator": "deep-translator",
    }
    optional = {
        "pynput"         : "pynput",           # keyboard listener
        "transformers"   : "transformers",     # MarianMT en→ml
        "gtts"           : "gTTS",             # TTS
        "pyttsx3"        : "pyttsx3",          # offline TTS fallback
        "scipy"          : "scipy",            # optional WAV I/O for testing
    }
    missing_req, missing_opt = [], []

    for mod, pkg in required.items():
        try:
            __import__(mod)
            print(f"  ✓  {pkg}")
        except ImportError:
            print(f"  ✗  {pkg}  (required)")
            missing_req.append(pkg)

    for mod, pkg in optional.items():
        try:
            __import__(mod)
            print(f"  ✓  {pkg}  (optional)")
        except ImportError:
            print(f"  –  {pkg}  (optional — not installed)")
            missing_opt.append(pkg)

    if missing_req:
        print(f"\nInstalling missing required packages: {missing_req}")
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing_req)

    if missing_opt:
        ans = input(f"\nInstall optional packages {missing_opt}? [y/N] ").strip().lower()
        if ans == "y":
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing_opt)


# ──────────────────────────────────────────────────────────────
def download_silero_vad():
    print("\n[Silero VAD] Pre-caching model …")
    try:
        import torch
        torch.hub.load(
            "snakers4/silero-vad",
            "silero_vad",
            force_reload=False,
            verbose=False,
        )
        print("  ✓  Silero VAD cached")
    except Exception as e:
        print(f"  ⚠  Silero VAD cache failed ({e}). Will retry at runtime.")


# ──────────────────────────────────────────────────────────────
HAND_LANDMARKER_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
)

def download_hand_landmarker():
    dest = Path("hand_landmarker.task")
    if dest.exists():
        print(f"\n  ✓  hand_landmarker.task already present ({dest.stat().st_size // 1024} KB)")
        return
    print(f"\n[MediaPipe] Downloading hand_landmarker.task …")
    try:
        urllib.request.urlretrieve(HAND_LANDMARKER_URL, dest, _progress_hook)
        print(f"\n  ✓  hand_landmarker.task ({dest.stat().st_size // 1024} KB)")
    except Exception as e:
        print(f"\n  ⚠  Download failed: {e}")
        print("     Manual URL:", HAND_LANDMARKER_URL)


def _progress_hook(block_num, block_size, total_size):
    downloaded = block_num * block_size
    if total_size > 0:
        pct = min(100, int(downloaded / total_size * 100))
        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
        print(f"\r  [{bar}] {pct}%", end="", flush=True)


# ──────────────────────────────────────────────────────────────
def warmstart_whisper(model_size: str):
    print(f"\n[Whisper] Pre-loading '{model_size}' model …")
    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        ct     = "float16" if device == "cuda" else "int8"
        from faster_whisper import WhisperModel
        cache  = os.path.join(os.path.dirname(__file__), ".model_cache")
        WhisperModel(model_size, device=device, compute_type=ct, download_root=cache)
        print(f"  ✓  faster-whisper '{model_size}' ready ({device}/{ct})")
    except Exception as e:
        print(f"  ⚠  Whisper warm-start failed ({e}). Will load at runtime.")


# ──────────────────────────────────────────────────────────────
def system_summary():
    print("\n── System Summary ────────────────────────────────────────")
    try:
        import torch
        cuda = torch.cuda.is_available()
        print(f"  PyTorch  : {torch.__version__}")
        print(f"  CUDA     : {'yes — ' + torch.cuda.get_device_name(0) if cuda else 'no (CPU mode)'}")
        if cuda:
            mb = torch.cuda.get_device_properties(0).total_memory // (1024 ** 2)
            print(f"  GPU VRAM : {mb} MB")
    except ImportError:
        print("  PyTorch  : not installed")

    try:
        import sounddevice as sd
        devs = sd.query_devices()
        inputs = [d for d in devs if d["max_input_channels"] > 0]
        print(f"  Audio in : {len(inputs)} device(s) found")
    except Exception as e:
        print(f"  Audio in : error ({e})")

    try:
        import cv2
        print(f"  OpenCV   : {cv2.__version__}")
    except ImportError:
        print("  OpenCV   : not installed")

    try:
        import mediapipe as mp
        print(f"  MediaPipe: {mp.__version__}")
    except ImportError:
        print("  MediaPipe: not installed")

    print("──────────────────────────────────────────────────────────\n")


# ──────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="base", choices=["tiny","base","small"])
    p.add_argument("--skip-packages", action="store_true")
    args = p.parse_args()

    print("═" * 60)
    print("  Real-Time Translator — Setup")
    print("═" * 60)

    check_python()

    if not args.skip_packages:
        print("\n[Packages]")
        check_packages()

    download_silero_vad()
    download_hand_landmarker()
    warmstart_whisper(args.model)
    system_summary()

    print("✅  Setup complete. Run:  python main.py\n")


if __name__ == "__main__":
    main()
