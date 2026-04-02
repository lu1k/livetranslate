# Real-Time Malayalam ↔ English Translator
### with ISL Sign Language Integration

A fully concurrent, low-latency pipeline for bidirectional speech translation
and Indian Sign Language (ISL) detection — all running locally.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          SYSTEM OVERVIEW                                 │
│                                                                          │
│   ┌──────────────┐  audio_queue  ┌────────────────────────┐             │
│   │ AudioModule  │──────────────►│  STTTranslationModule  │──┐          │
│   │              │               │                          │  │          │
│   │ • sounddevice│               │ • faster-whisper         │  │          │
│   │ • Silero VAD │               │ • ml→en (translate task) │  │ result  │
│   │ • Noise Redux│               │ • en→ml (MarianMT/Google)│  │ _queue  │
│   └──────────────┘               └────────────────────────┘  │          │
│                                                                │          │
│   ┌──────────────┐                                            ├─►┌──────────────┐  ┌──────────────┐
│   │  SignLanguage │──────── result_queue ──────────────────────┘  │  Integrator  │─►│ OutputModule │
│   │   Module      │                                               │              │  │              │
│   │ • OpenCV      │                                               │ • Arbitration│  │ • CLI render │
│   │ • MediaPipe   │                                               │ • Direction  │  │ • JSONL log  │
│   │ • ISL Heuristic│                                              │   switching  │  │ • TTS (opt.) │
│   └──────────────┘                                               └──────────────┘  └──────────────┘
└─────────────────────────────────────────────────────────────────────────┘
```

### Module responsibilities

| Module | Thread | Key library | Approx. latency |
|--------|--------|-------------|-----------------|
| AudioModule | sounddevice C thread | sounddevice, Silero VAD | <1 ms/chunk |
| STTTranslationModule | 1 worker thread | faster-whisper (CTranslate2) | 150–800 ms per utterance |
| SignLanguageModule | 1 camera thread | OpenCV, MediaPipe | ~30 ms/frame |
| Integrator | 1 dispatch thread | — | <1 ms |
| OutputModule | main + 1 TTS thread | — | <5 ms |

---

## Quick Start

### 1. Clone / download

```bash
git clone <your-repo>
cd realtime_translator
```

### 2. (Optional but recommended) Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
```

### 3. Install dependencies

**CPU only:**
```bash
pip install -r requirements.txt
```

**NVIDIA GPU (CUDA 12.1):**
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
```

**Apple Silicon (MPS):**
```bash
pip install torch torchvision torchaudio
pip install -r requirements.txt
```
> Note: faster-whisper uses CTranslate2; MPS acceleration falls back to CPU
> for CT2 ops. Performance is still very good on M-series chips.

### 4. Run setup (downloads models)

```bash
python setup.py                  # uses 'base' model
python setup.py --model small    # downloads 'small' for better Malayalam accuracy
```

This will:
- Cache Silero VAD via `torch.hub`
- Download `hand_landmarker.task` from Google MediaPipe CDN (~8 MB)
- Pre-download faster-whisper model weights (~74 MB for base)

### 5. Run

```bash
# Default: Malayalam speech → English text
python main.py

# English speech → Malayalam text
python main.py --direction en->ml

# Fastest setup (no camera, tiny model)
python main.py --no-sign --model tiny

# Best accuracy (GPU recommended)
python main.py --model small

# With TTS (speaks translated output aloud)
python main.py --tts

# Speech only, no sign language window
python main.py --no-sign

# Sign language only
python main.py --no-audio
```

---

## Runtime keyboard shortcuts

| Key | Action |
|-----|--------|
| `m` | Switch to **Malayalam → English** |
| `e` | Switch to **English → Malayalam** |
| `d` | Print diagnostics (queue depths, latency) |
| `q` | Quit cleanly |

> If `pynput` is not installed, press key + Enter.

---

## Sign Language Module

The sign language module integrates the ISL heuristic classifier from
[Jesna05/Live_Translate](https://github.com/Jesna05/Live_Translate).

### Optional CNN model

If you have a trained `sign_language_model.h5`, place it in the project root.
The module auto-detects it and uses the CNN classifier instead of heuristics.

### hand_landmarker.task

This 8 MB file is downloaded automatically by `setup.py`. If the download
fails, get it manually:

```
https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task
```

Place it in the project root (same directory as `main.py`).

---

## CLI Output Format

```
═══════════════════════════════════════════════════════════════════════════
  Malayalam ↔ English Real-Time Translator
  Log: translation_log.jsonl   TTS: off
═══════════════════════════════════════════════════════════════════════════
Mode      Lang        Latency  Output
──────────────────────────────────────────────────────────────────────────
SPEECH  ml→en   312.4ms  Hello, how are you?  [നമസ്കാരം, സുഖമാണോ?]
SPEECH  en→ml   287.1ms  സുപ്രഭാതം  [Good morning]
SIGN    isl→en    0.0ms  HELLO
```

---

## Performance Tuning

### Model selection

| Model | Size | CPU speed | GPU speed | Malayalam accuracy |
|-------|------|-----------|-----------|-------------------|
| `tiny` | 39 MB | ~0.3s | ~0.1s | Fair |
| `base` | 74 MB | ~0.6s | ~0.15s | Good ✓ |
| `small` | 244 MB | ~1.5s | ~0.3s | Best |

### Audio chunk size
In `config.py`, `CHUNK_DURATION_MS = 30` is the minimum VAD frame size
(one Silero frame). Increasing it reduces callback frequency but adds latency.

### VAD threshold
Increase `VAD_THRESHOLD` (→ 0.7) in noisy environments to reduce false
positives. Decrease (→ 0.3) for quiet environments or soft speech.

### Silence timeout
`SILENCE_THRESHOLD_MS = 600` means the pipeline waits 600 ms of silence
before flushing a segment to Whisper. Reduce to 300–400 ms for more
responsive (but potentially incomplete) transcriptions.

---

## Project Structure

```
realtime_translator/
├── main.py                    # Entry point + integrator + arbitration
├── config.py                  # All tunable parameters
├── setup.py                   # One-time model download script
├── requirements.txt
├── modules/
│   ├── audio_module.py        # Microphone → VAD → speech segments
│   ├── stt_translation_module.py  # Whisper + MarianMT/Google translate
│   ├── sign_language_module.py    # ISL heuristic + optional CNN
│   └── output_module.py       # CLI render, logging, TTS
├── .model_cache/              # faster-whisper weights (auto-created)
├── hand_landmarker.task       # MediaPipe task file (auto-downloaded)
└── translation_log.jsonl      # Output log (auto-created)
```

---

## Standalone module testing

Each module can be tested independently:

```bash
# Test audio capture + VAD
python -m modules.audio_module

# Test STT pipeline (inserts a silent dummy segment)
python -m modules.stt_translation_module

# Test sign language camera
python -m modules.sign_language_module

# Test output rendering
python -m modules.output_module
```

---

## Extending the System

### Add a new output language
1. Update `config.py` with the new language code.
2. In `stt_translation_module.py`, add a branch in `_transcribe_and_translate`.
3. MarianMT supports 100+ languages via the `opus-mt-en-mul` model.

### Swap in a different ASR model
The `STTTranslationModule` wraps faster-whisper. To swap it out, replace
the `_transcribe_and_translate` method with any model that consumes a
`numpy float32` array and returns a string.

### Add Bluetooth / remote output
In `output_module.py`, add a socket writer alongside the existing CLI printer.

---

## Troubleshooting

**No audio input detected**
```bash
python -c "import sounddevice; print(sounddevice.query_devices())"
```
Set `SIGN_CAMERA_INDEX` or the default device in sounddevice if needed.

**CUDA out of memory with `small` model**
Use `--model base` or set `WHISPER_COMPUTE_TYPE = "int8"` in config.py.

**hand_landmarker.task missing**
Run `python setup.py` or download manually (URL in setup.py).

**Malayalam text not rendering in terminal**
Your terminal must support Unicode. On Windows, run:
```
chcp 65001
```
or use Windows Terminal / VS Code terminal.

**gTTS/mpg123 not found for TTS**
On Linux: `sudo apt install mpg123`
On macOS: `afplay` is built-in (no install needed).

---

## License

This project integrates:
- [Silero VAD](https://github.com/snakers4/silero-vad) — MIT
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — MIT
- [MediaPipe](https://github.com/google/mediapipe) — Apache 2.0
- [ISL heuristic classifier](https://github.com/Jesna05/Live_Translate) — original author's license
