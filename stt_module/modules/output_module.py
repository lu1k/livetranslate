"""
modules/output_module.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Handles all output concerns:
  • Rich CLI rendering (ANSI colours, minimal / fast)
  • Optional TTS playback (gTTS async or pyttsx3 sync)
  • JSONL log file

All output operations are non-blocking from the caller's perspective;
TTS is queued in a background thread.

Standalone test:
    python -m modules.output_module
"""

from __future__ import annotations

import json
import queue
import threading
import time
from typing import Optional

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from modules.stt_translation_module import TranslationResult

# ──────────────────────────────────────────────────────────────
# ANSI colour helpers
# ──────────────────────────────────────────────────────────────
_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_CYAN   = "\033[36m"
_GREEN  = "\033[32m"
_YELLOW = "\033[33m"
_MAGENTA= "\033[35m"
_RED    = "\033[31m"
_DIM    = "\033[2m"

def _c(text, *codes):
    return "".join(codes) + str(text) + _RESET


# ──────────────────────────────────────────────────────────────
# TTS Backend
# ──────────────────────────────────────────────────────────────
class _TTSWorker:
    """
    Background thread that speaks translated text.
    Uses gTTS (Google TTS, high quality, requires internet) or
    pyttsx3 (offline, lower quality).
    """
    def __init__(self, engine: str = config.TTS_ENGINE):
        self._q: queue.Queue[tuple[str, str]] = queue.Queue(maxsize=5)
        self._engine = engine
        self._thread = threading.Thread(target=self._run, daemon=True, name="TTS")
        self._thread.start()

    def speak(self, text: str, lang: str = "en"):
        """Non-blocking; drops if queue full."""
        try:
            self._q.put_nowait((text, lang))
        except queue.Full:
            pass  # discard — output is time-sensitive, stale speech is worse than silence

    def _run(self):
        while True:
            try:
                text, lang = self._q.get(timeout=1.0)
            except queue.Empty:
                continue
            try:
                if self._engine == "gtts":
                    self._speak_gtts(text, lang)
                else:
                    self._speak_pyttsx3(text)
            except Exception as e:
                print(f"[TTS] Error: {e}")

    @staticmethod
    def _speak_gtts(text: str, lang: str):
        import tempfile, subprocess
        from gtts import gTTS
        tts = gTTS(text=text, lang=lang, slow=False)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tts.save(f.name)
            tmp = f.name
        # Play with platform-native player (non-blocking sub-process)
        if sys.platform == "darwin":
            subprocess.Popen(["afplay", tmp])
        elif sys.platform.startswith("linux"):
            subprocess.Popen(["mpg123", "-q", tmp])
        else:
            subprocess.Popen(["start", "/min", tmp], shell=True)

    @staticmethod
    def _speak_pyttsx3(text: str):
        import pyttsx3
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()


# ──────────────────────────────────────────────────────────────
# OutputModule
# ──────────────────────────────────────────────────────────────
class OutputModule:
    """
    Consume TranslationResult objects and produce output.

    Parameters
    ----------
    log_file  : str | None — path for JSONL log, or None to disable.
    tts       : bool       — enable TTS playback.
    """

    def __init__(
        self,
        log_file: Optional[str] = config.LOG_FILE if config.ENABLE_LOG else None,
        tts: bool = config.ENABLE_TTS,
    ):
        self._log_file  = log_file
        self._tts_worker: Optional[_TTSWorker] = _TTSWorker() if tts else None
        self._log_fh = None
        if log_file:
            os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
            self._log_fh = open(log_file, "a", encoding="utf-8", buffering=1)  # line-buffered

        self._session_count = 0
        self._session_start = time.time()
        self._print_header()

    # ────────────────────────────────────────────────────────
    # Public
    # ────────────────────────────────────────────────────────
    def emit(self, result: TranslationResult):
        """Called by the integrator whenever a result is ready."""
        self._session_count += 1
        self._print_result(result)
        if self._log_fh:
            self._log_result(result)
        if self._tts_worker and result.translated:
            self._tts_worker.speak(result.translated, lang=result.target_lang)

    def close(self):
        if self._log_fh:
            self._log_fh.close()
        elapsed = time.time() - self._session_start
        print(f"\n{_c('Session summary', _BOLD)}: "
              f"{self._session_count} outputs in {elapsed:.1f}s")

    # ────────────────────────────────────────────────────────
    # Rendering
    # ────────────────────────────────────────────────────────
    def _print_header(self):
        width = 72
        print("\n" + "═" * width)
        print(_c("  Malayalam ↔ English Real-Time Translator", _BOLD, _CYAN))
        print(_c(f"  Log: {self._log_file or 'disabled'}   "
                 f"TTS: {'on' if self._tts_worker else 'off'}", _DIM))
        print("═" * width)
        print(f"{'Mode':<8}  {'Lang':<8}  {'Latency':>9}  Output")
        print("─" * width)

    def _print_result(self, r: TranslationResult):
        mode_col = (
            _c("SIGN  ", _MAGENTA, _BOLD) if r.mode == "sign"
            else _c("SPEECH", _GREEN,   _BOLD)
        )
        lang_col  = _c(f"{r.source_lang}→{r.target_lang}", _YELLOW)
        lat_col   = _c(f"{r.latency_ms:>7.1f}ms", _DIM)

        # Source (dim, in brackets) + translation (bright)
        if r.source != r.translated:
            src_line = _c(f"[{r.source}]", _DIM)
            out_line = _c(r.translated,    _BOLD)
            print(f"{mode_col}  {lang_col}  {lat_col}  {out_line}  {src_line}")
        else:
            out_line = _c(r.source, _BOLD)
            print(f"{mode_col}  {lang_col}  {lat_col}  {out_line}")

    def _log_result(self, r: TranslationResult):
        record = {
            "ts"           : r.timestamp,
            "mode"         : r.mode,
            "direction"    : r.direction,
            "source_lang"  : r.source_lang,
            "target_lang"  : r.target_lang,
            "source"       : r.source,
            "translated"   : r.translated,
            "latency_ms"   : round(r.latency_ms, 2),
        }
        self._log_fh.write(json.dumps(record, ensure_ascii=False) + "\n")


# ──────────────────────────────────────────────────────────────
# Standalone test
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    out = OutputModule(log_file="/tmp/test_log.jsonl", tts=False)
    out.emit(TranslationResult(
        source="നമസ്കാരം", translated="Hello",
        source_lang="ml", target_lang="en",
        direction="ml->en", mode="speech", latency_ms=142.3,
    ))
    out.emit(TranslationResult(
        source="HELLO", translated="HELLO",
        source_lang="isl", target_lang="en",
        direction="sign->en", mode="sign", latency_ms=0.0,
    ))
    out.emit(TranslationResult(
        source="Good morning", translated="സുപ്രഭാതം",
        source_lang="en", target_lang="ml",
        direction="en->ml", mode="speech", latency_ms=210.7,
    ))
    out.close()
