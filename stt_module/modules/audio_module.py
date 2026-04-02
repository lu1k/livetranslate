"""
modules/audio_module.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Real-time microphone capture → noise reduction → normalisation
→ Silero VAD → speech-segment queue.

Design goals
  • One sounddevice InputStream callback per ~30 ms chunk (1 VAD frame).
  • Silero VAD runs in the callback thread — it is a tiny LSTM, ~0.3 ms/call.
  • Completed speech segments are placed on `speech_queue` (multiprocessing.Queue
    or queue.Queue) so the STT module can consume them without blocking audio.
  • No Python GIL contention: numpy ops + torch inference stay in C extensions.

Standalone test:
    python -m modules.audio_module
"""

from __future__ import annotations

import queue
import threading
import time
from collections import deque
from typing import Optional

import numpy as np
import sounddevice as sd
import torch
from scipy.signal import resample_poly
# Project config
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

# ──────────────────────────────────────────────────────────────
# Silero VAD loader (cached after first call)
# ──────────────────────────────────────────────────────────────
_vad_model: Optional[torch.nn.Module] = None
_vad_utils: Optional[dict] = None

def _load_silero_vad():
    global _vad_model, _vad_utils
    if _vad_model is not None:
        return _vad_model, _vad_utils
    # torch.hub caches the model locally after first download
    model, utils = torch.hub.load(
        repo_or_dir="snakers4/silero-vad",
        model="silero_vad",
        force_reload=False,
        onnx=False,           # PyTorch path — marginally faster on CPU for tiny chunks
        verbose=False,
    )
    _vad_model  = model
    _vad_utils  = utils
    return model, utils


# ──────────────────────────────────────────────────────────────
# Lightweight noise reduction  (spectral subtraction, real-time safe)
# ──────────────────────────────────────────────────────────────
class NoiseReducer:
    """
    Single-pass spectral subtraction with a running noise floor estimate.
    Operates on 16-bit equivalent float32 audio in the range [-1, 1].
    Latency: one chunk only (no look-ahead).
    """
    def __init__(self, sr: int = config.SAMPLE_RATE, n_fft: int = 512):
        self.n_fft      = n_fft
        self.hop        = n_fft // 2
        self.noise_floor: Optional[np.ndarray] = None
        self._alpha     = 0.98    # EMA smoothing for noise floor update
        self._beta      = 2.0     # over-subtraction factor

    def process(self, chunk: np.ndarray) -> np.ndarray:
        # Short chunks < n_fft: just normalise, skip spectral work
        if len(chunk) < self.n_fft:
            return chunk

        # RFFT on the chunk
        spectrum   = np.fft.rfft(chunk, n=self.n_fft)
        magnitude  = np.abs(spectrum)
        phase      = np.angle(spectrum)

        # Initialise or update noise floor (EMA of magnitude)
        if self.noise_floor is None:
            self.noise_floor = magnitude.copy()
        else:
            self.noise_floor = self._alpha * self.noise_floor + (1 - self._alpha) * magnitude

        # Spectral subtraction with half-wave rectification
        clean_mag = np.maximum(magnitude - self._beta * self.noise_floor, 0.0)

        # Reconstruct
        clean_spectrum = clean_mag * np.exp(1j * phase)
        out = np.fft.irfft(clean_spectrum, n=self.n_fft)
        # Return same length as input (trim or zero-pad)
        return out[: len(chunk)].astype(np.float32)


# ──────────────────────────────────────────────────────────────
# AudioModule
# ──────────────────────────────────────────────────────────────
class AudioModule:
    """
    Captures microphone audio, applies noise reduction + normalisation,
    runs Silero VAD per 30-ms frame, and emits completed speech segments
    onto `speech_queue`.

    Parameters
    ----------
    speech_queue : queue.Queue
        Thread-safe queue consumed by the STT module.
        Each item is a numpy float32 array at 16 kHz.
    """

    def __init__(self, speech_queue: queue.Queue):
        self.speech_queue   = speech_queue
        self.running        = False

        # Silero VAD
        self._vad_model, _  = _load_silero_vad()
        self._vad_model.eval()
        # Reset per-stream hidden state
        self._vad_model.reset_states()

        # Noise reducer
        self._noise_reducer = NoiseReducer()

        # Rolling speech accumulation buffer
        self._speech_buf: list[np.ndarray] = []
        self._speech_buf_samples: int = 0
        self._max_buf_samples = int(config.SPEECH_BUFFER_MAX_SEC * config.SAMPLE_RATE)

        # Silence tracking
        self._silence_samples   = 0
        self._silence_threshold = int(config.SILENCE_THRESHOLD_MS * config.SAMPLE_RATE / 1000)
        self._in_speech         = False

        # ── timing / diagnostics ──
        self._last_callback_ns: int = 0
        self._callback_jitter_ms: float = 0.0

        self._stream: Optional[sd.InputStream] = None
        self._lock = threading.Lock()  # guards _speech_buf
        self.raw_audio_queue = queue.Queue(maxsize=200)

    # ────────────────────────────────────────────────────────
    # sounddevice callback  (runs in a dedicated C thread)
    # ────────────────────────────────────────────────────────
    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            if status.input_overflow:
                return
            print(f"[Audio] ⚠ {status}")

        try:
            self.raw_audio_queue.put_nowait(indata[:, 0].copy())
        except queue.Full:
            pass

    # Worker thread
    def _processing_worker(self):
        TARGET_SAMPLES = 512

        while self.running:
            try:
                chunk = self.raw_audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            # ── resample 44100 → 16000 ──
            chunk = resample_poly(chunk, 16000, 44100).astype(np.float32)

            # ── noise reduction ──
            chunk = self._noise_reducer.process(chunk)

            # ── normalisation ──
            peak = np.abs(chunk).max()
            if peak > 1e-6:
                chunk = chunk / peak * 0.95

            # ── enforce fixed size ──
            if len(chunk) < TARGET_SAMPLES:
                chunk = np.pad(chunk, (0, TARGET_SAMPLES - len(chunk)))
            else:
                chunk = chunk[:TARGET_SAMPLES]

            # ── VAD ──
            tensor = torch.from_numpy(chunk).unsqueeze(0)

            with torch.no_grad():
                speech_prob = self._vad_model(tensor, 16000).item()

            is_speech = speech_prob >= config.VAD_THRESHOLD

            # ── same accumulation logic (copied from your callback) ──
            with self._lock:
                if is_speech:
                    self._in_speech = True
                    self._silence_samples = 0
                    self._speech_buf.append(chunk)
                    self._speech_buf_samples += len(chunk)
                else:
                    if self._in_speech:
                        self._speech_buf.append(chunk)
                        self._speech_buf_samples += len(chunk)
                        self._silence_samples += len(chunk)

                        silence_duration_ms = self._silence_samples / 16000 * 1000  # ✅ FIXED
                        if silence_duration_ms >= config.SILENCE_THRESHOLD_MS:
                            self._flush_segment()

                if self._speech_buf_samples >= self._max_buf_samples:
                    self._flush_segment()


    def _flush_segment(self):
        """Concatenate accumulated chunks and push to STT queue. Called under lock."""
        if not self._speech_buf:
            return
        segment = np.concatenate(self._speech_buf, axis=0)
        self._speech_buf.clear()
        self._speech_buf_samples = 0
        self._in_speech = False
        self._silence_samples = 0

        # Non-blocking put — drop if queue full (back-pressure safety valve)
        try:
            self.speech_queue.put_nowait(segment)
        except queue.Full:
            print("[Audio] ⚠  STT queue full — dropping segment")

    # ────────────────────────────────────────────────────────
    # Public API
    # ────────────────────────────────────────────────────────
    def start(self):
        """Open sounddevice stream and begin processing."""
        print(f"[Audio] Starting — {config.SAMPLE_RATE} Hz, "
              f"{config.CHUNK_DURATION_MS} ms chunks, "
              f"VAD threshold={config.VAD_THRESHOLD}")
        self._stream = sd.InputStream(
            samplerate=44100,
            channels=1,
            dtype="float32",

            # 🔥 KEY FIXES
            blocksize=config.CHUNK_SAMPLES * 4,   # bigger buffer
            latency="high",                      # prevent overflow

            callback=self._audio_callback,
        )
        self.worker_thread = threading.Thread(
            target=self._processing_worker,
            daemon=True
        )
        self.worker_thread.start()
        self.running = True
        self._stream.start()

    def stop(self):
        """Stop and close the stream cleanly."""
        self.running = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        # Flush any remaining buffer
        with self._lock:
            self._flush_segment()
        print(f"[Audio] Stopped. Avg callback jitter: {self._callback_jitter_ms:.2f} ms")

    def diagnostics(self) -> dict:
        return {
            "callback_jitter_ms": round(self._callback_jitter_ms, 3),
            "in_speech":          self._in_speech,
            "buf_samples":        self._speech_buf_samples,
        }


# ──────────────────────────────────────────────────────────────
# Standalone test
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import time

    q: queue.Queue = queue.Queue(maxsize=20)
    module = AudioModule(q)
    module.start()
    print("Speak now … press Ctrl-C to stop.\n")
    try:
        while True:
            try:
                seg = q.get(timeout=1.0)
                dur = len(seg) / config.SAMPLE_RATE
                print(f"  ✓ Speech segment captured: {dur:.2f}s  "
                      f"({len(seg)} samples)  "
                      f"jitter={module.diagnostics()['callback_jitter_ms']:.2f}ms")
            except queue.Empty:
                pass
    except KeyboardInterrupt:
        module.stop()
