"""
stt.py — Your Speech-to-Text script
====================================
vaani_server.py spawns this file as a subprocess and reads its stdout.

CONTRACT: print one transcript per line, flushed immediately.
    print("Hello world", flush=True)   ✓
    print("Next phrase",  flush=True)  ✓

That's the only requirement. The rest of this file is a working
example using SpeechRecognition + Google Web Speech API (free, no key).

Install deps:
    pip install SpeechRecognition pyaudio

On Linux you may also need:
    sudo apt install portaudio19-dev python3-pyaudio
"""

import sys
import speech_recognition as sr


def main():
    recognizer = sr.Recognizer()

    # Adjust for ambient noise once at startup
    with sr.Microphone() as source:
        print("[STT] Calibrating for ambient noise…", file=sys.stderr, flush=True)
        recognizer.adjust_for_ambient_noise(source, duration=1)
        print("[STT] Listening…", file=sys.stderr, flush=True)

        while True:
            try:
                audio = recognizer.listen(source, timeout=10, phrase_time_limit=15)
            except sr.WaitTimeoutError:
                # No speech detected in the window — keep looping
                continue

            try:
                text = recognizer.recognize_google(audio, language="en-IN")
                # ── THIS IS THE IMPORTANT PART ──────────────────────────────
                # Print the transcript on a single line, flushed immediately.
                # vaani_server.py reads this and forwards it to Electron.
                print(text, flush=True)
                # ────────────────────────────────────────────────────────────

            except sr.UnknownValueError:
                # Speech was heard but couldn't be understood
                pass
            except sr.RequestError as exc:
                print(f"[STT] API error: {exc}", file=sys.stderr, flush=True)
                sys.exit(1)


if __name__ == "__main__":
    main()
