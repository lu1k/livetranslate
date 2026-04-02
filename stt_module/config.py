"""
config.py — Centralised configuration for all modules.
Edit these values to tune performance on your hardware.
"""

# ──────────────────────────────────────────────
# Audio Module
# ──────────────────────────────────────────────
SAMPLE_RATE        = 44100          # Hz — Whisper & Silero VAD both expect 16 kHz
CHUNK_DURATION_MS  = 64            # ms per sounddevice callback (one VAD frame = 30 ms)
CHUNK_SAMPLES      = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)  # 1411 samples
AUDIO_CHANNELS     = 1
AUDIO_DTYPE        = "float32"

# Rolling buffer: accumulate speech until silence detected
SPEECH_BUFFER_MAX_SEC  = 8.0        # hard cap — flush even if no silence
SILENCE_THRESHOLD_MS   = 600        # ms of silence → flush segment to STT

# ──────────────────────────────────────────────
# Silero VAD
# ──────────────────────────────────────────────
VAD_THRESHOLD          = 0.5        # 0–1, higher = stricter
VAD_MIN_SPEECH_DURATION_MS   = 100  # ignore very short blips
VAD_MIN_SILENCE_DURATION_MS  = 300  # min silence before segment is closed

# ──────────────────────────────────────────────
# STT / Translation
# ──────────────────────────────────────────────
# "tiny" ≈ 39 MB   — fastest, use when GPU not available
# "base" ≈ 74 MB   — good balance
# "small" ≈ 244 MB — better Malayalam accuracy, needs GPU
WHISPER_MODEL_SIZE  = "base"        # override via CLI: --model tiny|base|small
WHISPER_DEVICE      = "auto"        # "auto" | "cuda" | "cpu"
WHISPER_COMPUTE_TYPE = "auto"       # "auto" | "float16" | "int8" | "float32"

# Language codes (BCP-47)
LANG_MALAYALAM = "ml"
LANG_ENGLISH   = "en"

# Default translation direction: "ml->en" or "en->ml"
DEFAULT_DIRECTION = "ml->en"

# ──────────────────────────────────────────────
# Sign Language Module
# ──────────────────────────────────────────────
SIGN_CAMERA_INDEX      = 0
SIGN_FRAME_WIDTH       = 640
SIGN_FRAME_HEIGHT      = 480
SIGN_STABLE_FRAMES     = 6          # frames a gesture must be held before acceptance
SIGN_COOLDOWN_FRAMES   = 8          # frames to skip after accepting a letter

# Path to optional pre-trained .h5 model (set to "" to use heuristic classifier)
SIGN_MODEL_PATH        = "sign_language_model.h5"

# ──────────────────────────────────────────────
# Integration / Arbitration
# ──────────────────────────────────────────────
# How long (seconds) sign-language input stays "active" after last gesture
SIGN_ACTIVE_TIMEOUT_SEC = 3.0

# ──────────────────────────────────────────────
# Output
# ──────────────────────────────────────────────
ENABLE_TTS     = False              # set True to speak translated text aloud
TTS_ENGINE     = "gtts"            # "gtts" | "pyttsx3"
ENABLE_LOG     = True
LOG_FILE       = "translation_log.jsonl"  # one JSON object per line
