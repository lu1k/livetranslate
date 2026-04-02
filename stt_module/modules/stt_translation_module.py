"""
modules/stt_translation_module.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Speech-to-Text (faster-whisper) + translation pipeline.

Responsibilities
  • Consume audio segments from `speech_queue`.
  • Auto-detect or use configured language direction.
  • Transcribe with faster-whisper (CTranslate2 backend).
  • Translate:
      – ml → en: Whisper's built-in translation task (single pass, fastest).
      – en → ml: Whisper transcribe in English + Helsinki-NLP MarianMT
                 (or deep-translator fallback if no GPU for MarianMT).
  • Push results onto `result_queue` as TranslationResult dataclasses.

Design choices for low latency
  • faster-whisper uses CTranslate2 (quantised int8/float16) — 2–4× faster
    than openai-whisper on CPU; GPU gives another 3–5×.
  • `beam_size=1` + `best_of=1` trades a tiny accuracy drop for speed.
  • `vad_filter=False` because our audio module already strips silence.
  • Translation direction is a hot-swappable attribute — no restart needed.

Standalone test:
    python -m modules.stt_translation_module
"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

# ──────────────────────────────────────────────────────────────
# Result dataclass shared between all modules
# ──────────────────────────────────────────────────────────────
@dataclass
class TranslationResult:
    source          : str       = ""      # original transcription
    translated      : str       = ""      # translated text
    source_lang     : str       = ""      # detected / configured language code
    target_lang     : str       = ""
    direction       : str       = ""      # "ml->en" | "en->ml"
    mode            : str       = "speech"  # "speech" | "sign"
    latency_ms      : float     = 0.0
    timestamp       : float     = field(default_factory=time.time)


# ──────────────────────────────────────────────────────────────
# Device / compute-type helpers
# ──────────────────────────────────────────────────────────────
def _resolve_device_and_compute() -> tuple[str, str]:
    """
    Automatically pick the best device + quantisation for faster-whisper.
    Returns (device, compute_type).
    """
    import torch
    if config.WHISPER_DEVICE != "auto":
        dev = config.WHISPER_DEVICE
    elif torch.cuda.is_available():
        dev = "cuda"
    else:
        dev = "cpu"

    if config.WHISPER_COMPUTE_TYPE != "auto":
        ct = config.WHISPER_COMPUTE_TYPE
    elif dev == "cuda":
        ct = "float16"   # GPU — full precision in fp16
    else:
        ct = "int8"      # CPU — int8 quantisation: ~2× faster, tiny accuracy delta

    return dev, ct


# ──────────────────────────────────────────────────────────────
# Optional MarianMT for en → ml
# ──────────────────────────────────────────────────────────────
class _MarianTranslator:
    """
    Helsinki-NLP/opus-mt-en-ml via HuggingFace transformers.
    Falls back to deep-translator (Google Translate API wrapper) if the
    model can't be loaded (e.g. no internet, transformers not installed).
    """
    def __init__(self):
        self._pipe = None
        self._fallback = False
        self._load()

    def _load(self):
        try:
            from transformers import pipeline as hf_pipeline
            print("[STT] Loading MarianMT (en→ml) …")
            self._pipe = hf_pipeline(
                "translation",
                model="Helsinki-NLP/opus-mt-en-mul",   # multilingual → covers ml
                # For a dedicated en→ml model use "Helsinki-NLP/opus-mt-en-ml"
                # but availability varies; opus-mt-en-mul is more reliable.
                device=-1,   # CPU for MarianMT (small model, fast enough)
                max_length=512,
            )
            print("[STT] MarianMT loaded ✓")
        except Exception as e:
            print(f"[STT] MarianMT unavailable ({e}), using deep-translator fallback.")
            self._fallback = True

    def translate(self, text: str) -> str:
        if self._fallback or self._pipe is None:
            return self._fallback_translate(text)
        try:
            result = self._pipe(text, src_lang="en", tgt_lang="ml")
            return result[0]["translation_text"]
        except Exception as e:
            print(f"[STT] MarianMT error ({e}), falling back.")
            return self._fallback_translate(text)

    @staticmethod
    def _fallback_translate(text: str) -> str:
        """Use deep-translator (free, no key) as last resort."""
        try:
            from deep_translator import GoogleTranslator
            return GoogleTranslator(source="en", target="ml").translate(text)
        except Exception as e:
            return f"[Translation error: {e}]"


# ──────────────────────────────────────────────────────────────
# STT + Translation Module
# ──────────────────────────────────────────────────────────────
class STTTranslationModule:
    """
    Parameters
    ----------
    speech_queue  : queue.Queue  — audio segments from AudioModule
    result_queue  : queue.Queue  — TranslationResult objects for the integrator
    direction     : str          — "ml->en" | "en->ml" (hot-swappable via .set_direction())
    """

    def __init__(
        self,
        speech_queue: queue.Queue,
        result_queue: queue.Queue,
        direction: str = config.DEFAULT_DIRECTION,
    ):
        self.speech_queue  = speech_queue
        self.result_queue  = result_queue
        self.direction     = direction
        self.running       = False
        self._thread: Optional[threading.Thread] = None

        # Diagnostics
        self._total_segments   = 0
        self._avg_latency_ms   = 0.0

        # ── Load faster-whisper ──────────────────────────────
        device, compute_type = _resolve_device_and_compute()
        print(f"[STT] Loading faster-whisper '{config.WHISPER_MODEL_SIZE}' "
              f"on {device} ({compute_type}) …")
        from faster_whisper import WhisperModel
        self._whisper = WhisperModel(
            config.WHISPER_MODEL_SIZE,
            device=device,
            compute_type=compute_type,
            num_workers=2,    # parallel CTranslate2 workers
            download_root=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".model_cache"),
        )
        print("[STT] faster-whisper ready ✓")

        # ── Load MarianMT for en→ml ──────────────────────────
        self._marian: Optional[_MarianTranslator] = None
        if direction == "en->ml":
            self._marian = _MarianTranslator()

    # ────────────────────────────────────────────────────────
    # Direction switching (thread-safe, no restart needed)
    # ────────────────────────────────────────────────────────
    def set_direction(self, direction: str):
        """Dynamically switch between 'ml->en' and 'en->ml'."""
        assert direction in ("ml->en", "en->ml"), "Unknown direction"
        self.direction = direction
        if direction == "en->ml" and self._marian is None:
            self._marian = _MarianTranslator()
        print(f"[STT] Direction switched to {direction}")

    # ────────────────────────────────────────────────────────
    # Core inference
    # ────────────────────────────────────────────────────────
    def _transcribe_and_translate(self, audio: np.ndarray) -> Optional[TranslationResult]:
        """
        Single inference call. Returns None if audio is too short/empty.

        ml → en:  Whisper `task="translate"` does transcription + translation
                  in one forward pass — lowest possible latency path.

        en → ml:  Whisper `task="transcribe"` in English, then MarianMT/Google
                  for the second hop.
        """
        t0 = time.perf_counter()

        # Silero already stripped silence, but guard against micro-segments
        duration_s = len(audio) / config.SAMPLE_RATE
        if duration_s < 0.3:
            return None

        direction = self.direction

        # ── Malayalam → English ─────────────────────────────
        if direction == "ml->en":
            segs, info = self._whisper.transcribe(
                audio,
                language="ml",          # force source language
                task="translate",       # built-in translation to English
                beam_size=1,            # fastest greedy decoding
                best_of=1,
                temperature=0.0,        # deterministic
                vad_filter=False,       # we already VAD-filtered
                without_timestamps=True,
            )
            source_text     = " ".join(s.text for s in segs).strip()
            translated_text = source_text   # "translate" task output is already English
            # For separate transcription of the Malayalam source, run a second
            # transcribe pass — we skip it here for latency.
            src_lang, tgt_lang = config.LANG_MALAYALAM, config.LANG_ENGLISH

        # ── English → Malayalam ─────────────────────────────
        else:
            segs, info = self._whisper.transcribe(
                audio,
                language="en",
                task="transcribe",
                beam_size=1,
                best_of=1,
                temperature=0.0,
                vad_filter=False,
                without_timestamps=True,
            )
            source_text = " ".join(s.text for s in segs).strip()

            # Translate English → Malayalam
            if self._marian is not None:
                translated_text = self._marian.translate(source_text)
            else:
                translated_text = f"[MarianMT not loaded]"
            src_lang, tgt_lang = config.LANG_ENGLISH, config.LANG_MALAYALAM

        latency_ms = (time.perf_counter() - t0) * 1000

        # Running average latency
        self._total_segments += 1
        n = self._total_segments
        self._avg_latency_ms = self._avg_latency_ms * (n - 1) / n + latency_ms / n

        if not source_text:
            return None

        return TranslationResult(
            source       = source_text,
            translated   = translated_text,
            source_lang  = src_lang,
            target_lang  = tgt_lang,
            direction    = direction,
            mode         = "speech",
            latency_ms   = latency_ms,
        )

    # ────────────────────────────────────────────────────────
    # Worker thread
    # ────────────────────────────────────────────────────────
    def _worker(self):
        print("[STT] Worker thread started.")
        while self.running:
            try:
                audio = self.speech_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            result = self._transcribe_and_translate(audio)
            if result is not None:
                try:
                    self.result_queue.put_nowait(result)
                except queue.Full:
                    print("[STT] ⚠  Result queue full — dropping result")

    # ────────────────────────────────────────────────────────
    # Public API
    # ────────────────────────────────────────────────────────
    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._worker, daemon=True, name="STT-Worker")
        self._thread.start()
        print(f"[STT] Started. Direction: {self.direction}")

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        print(f"[STT] Stopped. Segments processed: {self._total_segments}, "
              f"avg latency: {self._avg_latency_ms:.1f} ms")

    def diagnostics(self) -> dict:
        return {
            "direction"       : self.direction,
            "total_segments"  : self._total_segments,
            "avg_latency_ms"  : round(self._avg_latency_ms, 1),
        }


# ──────────────────────────────────────────────────────────────
# Standalone test (requires audio_module or a WAV file)
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import scipy.io.wavfile as wav

    speech_q: queue.Queue = queue.Queue()
    result_q: queue.Queue = queue.Queue()

    module = STTTranslationModule(speech_q, result_q, direction="ml->en")
    module.start()

    # Inject a short silence segment to verify the pipeline boots
    dummy = np.zeros(config.SAMPLE_RATE * 2, dtype=np.float32)  # 2 s silence
    speech_q.put(dummy)

    try:
        result = result_q.get(timeout=30)
        print(f"\n[Test] Transcription : {result.source}")
        print(f"[Test] Translation   : {result.translated}")
        print(f"[Test] Latency       : {result.latency_ms:.1f} ms")
    except queue.Empty:
        print("[Test] No result within 30 s (expected for silent audio).")

    module.stop()
