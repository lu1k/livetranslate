"""
main.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Entry point — wires all three modules together and runs the
arbitration loop.

Usage
─────
  python main.py                        # defaults (ml→en, base model)
  python main.py --direction en->ml     # English speech → Malayalam
  python main.py --direction ml->en --model tiny   # fastest
  python main.py --no-sign              # speech only (no camera)
  python main.py --no-audio             # sign only  (no microphone)
  python main.py --no-window            # hide OpenCV window

Direction can be toggled at runtime by pressing:
  'm'  → switch to ml→en
  'e'  → switch to en→ml
  'd'  → show diagnostics
  'q'  → quit

Pipeline Architecture
─────────────────────
  Microphone ──► AudioModule ──► speech_queue ──► STTTranslationModule ──┐
                                                                         ├─► result_queue ──► Integrator ──► OutputModule
  Camera ──────────────────────► SignLanguageModule ──────────────────────┘

Arbitration
──────────
  • If sign language has been active within SIGN_ACTIVE_TIMEOUT_SEC → emit sign result.
  • Otherwise emit speech result.
  • Both pipelines always run concurrently.
"""

from __future__ import annotations

import argparse
import queue
import signal
import sys
import threading
import time

import config

# ──────────────────────────────────────────────────────────────
# CLI argument parsing
# ──────────────────────────────────────────────────────────────
def _parse_args():
    p = argparse.ArgumentParser(
        description="Real-time Malayalam ↔ English speech + sign language translator"
    )
    p.add_argument(
        "--direction", "-d",
        choices=["ml->en", "en->ml"],
        default=config.DEFAULT_DIRECTION,
        help="Initial translation direction (default: %(default)s)",
    )
    p.add_argument(
        "--model", "-m",
        choices=["tiny", "base", "small"],
        default=config.WHISPER_MODEL_SIZE,
        help="Whisper model size (default: %(default)s)",
    )
    p.add_argument("--no-sign",   action="store_true", help="Disable sign language module")
    p.add_argument("--no-audio",  action="store_true", help="Disable audio/speech module")
    p.add_argument("--no-window", action="store_true", help="Hide OpenCV preview window")
    p.add_argument("--tts",       action="store_true", help="Enable text-to-speech output")
    p.add_argument("--log",       default=config.LOG_FILE, help="Path for JSONL log file")
    return p.parse_args()


# ──────────────────────────────────────────────────────────────
# Keyboard listener (non-blocking, cross-platform)
# ──────────────────────────────────────────────────────────────
class _KeyboardListener:
    """
    Non-blocking keyboard reader.  Uses `pynput` if available,
    otherwise falls back to a raw stdin thread (Unix only).
    """
    def __init__(self, callback):
        self._cb      = callback
        self._thread: threading.Thread | None = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True, name="Keyboard")
        self._thread.start()

    def _run(self):
        try:
            from pynput import keyboard
            with keyboard.Events() as events:
                for event in events:
                    if isinstance(event, keyboard.Events.Press) and hasattr(event.key, "char"):
                        self._cb(event.key.char)
        except ImportError:
            # Fallback: readline loop (works in most terminals)
            while True:
                try:
                    line = sys.stdin.readline().strip().lower()
                    if line:
                        self._cb(line[0])
                except (EOFError, OSError):
                    break


# ──────────────────────────────────────────────────────────────
# Integrator
# ──────────────────────────────────────────────────────────────
class Integrator:
    """
    Consumes result_queue (fed by both STT and sign modules),
    applies arbitration, and forwards to OutputModule.

    Arbitration rules
    -----------------
    1. If sign language has been active recently → pass sign results through
       and suppress speech results.
    2. Otherwise pass speech results through and ignore empty sign queue.
    3. Both pipelines always run — only the output filter differs.
    """

    def __init__(self, result_queue: queue.Queue, sign_module, output_module, stt_module):
        self.result_queue  = result_queue
        self.sign_module   = sign_module
        self.output_module = output_module
        self.stt_module    = stt_module
        self.running       = False
        self._thread: threading.Thread | None = None

    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="Integrator")
        self._thread.start()

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=3)

    def _run(self):
        while self.running:
            try:
                result = self.result_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            # ── Arbitration ─────────────────────────────────
            sign_active = (
                self.sign_module is not None and self.sign_module.is_active
            )

            if result.mode == "sign":
                # Sign result: always emit when sign is active
                if sign_active:
                    self.output_module.emit(result)

            else:  # speech
                # Speech result: suppress if sign is active
                if not sign_active:
                    self.output_module.emit(result)

    def set_direction(self, direction: str):
        if self.stt_module:
            self.stt_module.set_direction(direction)


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────
def main():
    args = _parse_args()

    # Apply CLI overrides to config
    config.WHISPER_MODEL_SIZE = args.model
    config.DEFAULT_DIRECTION  = args.direction
    config.ENABLE_TTS         = args.tts

    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║  Malayalam ↔ English Real-Time Translator                ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"  Direction : {args.direction}")
    print(f"  Model     : {args.model}")
    print(f"  Audio     : {'disabled' if args.no_audio else 'enabled'}")
    print(f"  Sign      : {'disabled' if args.no_sign  else 'enabled'}")
    print(f"  TTS       : {'on' if args.tts else 'off'}")
    print(f"  Log       : {args.log}\n")
    print("  Keyboard shortcuts (press + Enter if pynput not installed):")
    print("    m  →  switch to Malayalam→English")
    print("    e  →  switch to English→Malayalam")
    print("    d  →  show diagnostics")
    print("    q  →  quit\n")

    # ── Shared queues ────────────────────────────────────────
    # speech_queue: raw audio segments (numpy arrays)
    # result_queue: TranslationResult objects from both pipelines
    speech_queue : queue.Queue = queue.Queue(maxsize=10)
    result_queue : queue.Queue = queue.Queue(maxsize=50)

    # ── Modules ──────────────────────────────────────────────
    audio_module    = None
    stt_module      = None
    sign_module     = None

    if not args.no_audio:
        from modules.audio_module import AudioModule
        audio_module = AudioModule(speech_queue)

    if not args.no_audio:
        from modules.stt_translation_module import STTTranslationModule
        stt_module = STTTranslationModule(
            speech_queue, result_queue, direction=args.direction
        )

    if not args.no_sign:
        from modules.sign_language_module import SignLanguageModule
        sign_module = SignLanguageModule(
            result_queue, show_window=not args.no_window
        )

    from modules.output_module import OutputModule
    output_module = OutputModule(log_file=args.log, tts=args.tts)

    integrator = Integrator(result_queue, sign_module, output_module, stt_module)

    # ── Start all modules ────────────────────────────────────
    integrator.start()
    if stt_module:
        stt_module.start()
    if audio_module:
        audio_module.start()
    if sign_module:
        sign_module.start()

    # ── Keyboard handler ─────────────────────────────────────
    def on_key(char):
        if char == "q":
            stop_all()
        elif char == "m":
            integrator.set_direction("ml->en")
            print("\n  [→] Direction: Malayalam → English")
        elif char == "e":
            integrator.set_direction("en->ml")
            print("\n  [→] Direction: English → Malayalam")
        elif char == "d":
            print("\n  ── Diagnostics ──────────────────────────────────────")
            if audio_module:
                print(f"     Audio : {audio_module.diagnostics()}")
            if stt_module:
                print(f"     STT   : {stt_module.diagnostics()}")
            print(f"     speech_q size : {speech_queue.qsize()}")
            print(f"     result_q size : {result_queue.qsize()}")
            print("  ─────────────────────────────────────────────────────\n")

    kb = _KeyboardListener(on_key)
    kb.start()

    # ── Graceful shutdown ────────────────────────────────────
    _shutdown_event = threading.Event()

    def stop_all(*_):
        if _shutdown_event.is_set():
            return
        _shutdown_event.set()
        print("\n[Main] Shutting down …")
        integrator.stop()
        if audio_module:
            audio_module.stop()
        if stt_module:
            stt_module.stop()
        if sign_module:
            sign_module.stop()
        output_module.close()

    signal.signal(signal.SIGINT,  stop_all)
    signal.signal(signal.SIGTERM, stop_all)

    print("[Main] All modules running. Press Ctrl-C or 'q' to stop.\n")

    # ── Main thread: wait for shutdown ───────────────────────
    try:
        while not _shutdown_event.is_set():
            time.sleep(0.1)
    except KeyboardInterrupt:
        stop_all()


if __name__ == "__main__":
    main()
