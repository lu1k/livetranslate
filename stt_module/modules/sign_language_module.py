"""
modules/sign_language_module.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ISL (Indian Sign Language) / ASL heuristic + optional CNN classifier.

Adapted from: https://github.com/Jesna05/Live_Translate/blob/main/main.py

Changes vs. original
  • Runs in its own thread — communicates via result_queue only.
  • No tkinter popup (results pushed to CLI via queue).
  • Optional model path from config (falls back to heuristic).
  • Activity tracking: sets `last_gesture_time` so the integrator can
    apply the sign-language priority timeout.
  • cv2.imshow is kept but guarded by SHOW_WINDOW flag.

Standalone test:
    python -m modules.sign_language_module
"""

from __future__ import annotations

import queue
import threading
import time
import os
from typing import Optional

import cv2
import numpy as np
import mediapipe as mp

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"   # suppress TensorFlow noise

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

# Import the shared result type from the STT module
from modules.stt_translation_module import TranslationResult

# ──────────────────────────────────────────────────────────────
# Optional: load Keras model if available
# ──────────────────────────────────────────────────────────────
def _try_load_keras_model(path: str):
    if not path or not os.path.exists(path):
        return None
    try:
        from tensorflow.keras.models import load_model
        model = load_model(path, compile=False)
        print(f"[Sign] Loaded Keras model from {path}")
        return model
    except Exception as e:
        print(f"[Sign] Could not load Keras model ({e}) — using heuristic classifier.")
        return None


# ──────────────────────────────────────────────────────────────
# ISL heuristic classifier (ported verbatim from original)
# ──────────────────────────────────────────────────────────────
def _fingers_up(hand):
    tips = [8, 12, 16, 20]
    pips = [6, 10, 14, 18]
    return [hand[tip].y < hand[pip].y for tip, pip in zip(tips, pips)]


def _dist(lm1, lm2):
    return ((lm1.x - lm2.x) ** 2 + (lm1.y - lm2.y) ** 2) ** 0.5


def _heuristic_classify(hands) -> str:
    """
    Pure ISL heuristic — no model weights required.
    Returns a letter/word string or "" if no gesture recognized.
    """
    letter = ""

    if len(hands) == 1:
        h1 = hands[0]
        f1 = _fingers_up(h1)
        thumb_ext = abs(h1[4].x - h1[2].x) > 0.05
        thumb_up  = h1[4].y < h1[3].y
        dist_o    = _dist(h1[4], h1[8])

        if f1 == [False, False, False, False]:
            if thumb_ext and thumb_up:
                letter = " "
            elif thumb_ext and not thumb_up and h1[4].y > h1[8].y:
                letter = "?"
            elif h1[8].y > h1[6].y and h1[8].y < h1[5].y and not thumb_ext:
                letter = ","
            elif dist_o < 0.06:
                letter = "O"
            elif _dist(h1[4], h1[8]) > 0.08 and h1[8].x > h1[0].x:
                letter = "C"
        elif f1 == [True, False, False, False]:
            if h1[8].y > h1[5].y and h1[0].y < h1[9].y:
                letter = "!"
        elif f1 == [False, False, False, True]:
            letter = "BACKSPACE"
        elif f1 == [True, True, False, False]:
            if _dist(h1[8], h1[12]) > 0.05:
                letter = " "
            else:
                letter = "U"
        elif f1 == [True, True, True, True]:
            if _dist(h1[8], h1[12]) > 0.05 or _dist(h1[12], h1[16]) > 0.05:
                letter = "HELLO"

    elif len(hands) == 2:
        h1, h2 = hands[0], hands[1]
        f1, f2 = _fingers_up(h1), _fingers_up(h2)

        f_fist = [False, False, False, False]
        f_open = [True, True, True, True]
        f_idx  = [True, False, False, False]

        h1_fist = f1 == f_fist; h2_fist = f2 == f_fist
        h1_open = f1 == f_open; h2_open = f2 == f_open
        h1_idx  = f1 == f_idx;  h2_idx  = f2 == f_idx

        dist_8_8 = _dist(h1[8], h2[8])
        dist_0_0 = _dist(h1[0], h2[0])

        if h1_idx and h2_idx:
            if _dist(h1[8], h2[5]) < 0.12 or _dist(h2[8], h1[5]) < 0.12:
                letter = "Y"
            elif dist_8_8 < 0.06:
                letter = "E"
            elif _dist(h1[6], h2[6]) < 0.08:
                letter = "X"
            elif _dist(h1[8], h2[6]) < 0.08 or _dist(h2[8], h1[6]) < 0.08:
                letter = "K"
            elif dist_8_8 < 0.14:
                letter = "R"

        elif h1_open and h2_open:
            if dist_0_0 < 0.35 and dist_8_8 > 0.06:
                letter = "H"
            elif dist_8_8 < 0.06 and _dist(h1[12], h2[12]) < 0.06:
                letter = "W"
            elif _dist(h1[9], h2[9]) < 0.1:
                letter = "Z"

        elif h1_fist and h2_fist:
            if dist_0_0 < 0.15:
                letter = "G"
            elif dist_8_8 < 0.1:
                letter = "B"
            elif _dist(h1[8], h2[4]) < 0.1 or _dist(h2[8], h1[4]) < 0.1:
                letter = "Q"

        elif (h1_idx and h2_fist) or (h2_idx and h1_fist):
            fist = h1 if h1_fist else h2
            idx  = h2 if h1_fist else h1
            if _dist(fist[8], idx[8]) < 0.1:
                letter = "P"
            elif _dist(fist[8], idx[5]) < 0.1:
                letter = "D"

        elif f1 == [False, False, False, True] and f2 == [False, False, False, True]:
            if _dist(h1[20], h2[20]) < 0.12:
                letter = "S"

        elif f1[:2] == [True, True] and f2[:2] == [True, True]:
            if dist_8_8 < 0.12:
                letter = "F"

        elif h1_open or h2_open:
            if h1_open and not h2_open:
                palm, other, f_other = h1, h2, f2
            else:
                palm, other, f_other = h2, h1, f1
            palm_base = palm[0]
            if f_other == [False, False, False, True] and _dist(other[20], palm_base) < 0.15:
                letter = "I"
            elif f_other == [True, False, False, False]:
                if _dist(other[8], palm_base) < 0.15:
                    letter = "T"
                elif abs(other[4].x - other[2].x) > 0.05 and _dist(other[8], palm_base) < 0.2:
                    letter = "L"
            elif f_other == [True, True, True, False] and _dist(other[12], palm_base) < 0.15:
                letter = "M"
            elif f_other == [True, True, False, False]:
                if _dist(other[8], other[12]) > 0.05 and _dist(other[8], palm_base) < 0.15:
                    letter = "V"
                elif _dist(other[8], palm_base) < 0.15:
                    letter = "N"

        # A cross
        if letter == "" and not (h1_open and h2_open):
            if _dist(h1[8], h2[4]) < 0.08 or _dist(h2[8], h1[4]) < 0.08:
                letter = "A"

    return letter


# ──────────────────────────────────────────────────────────────
# Sign Language Module
# ──────────────────────────────────────────────────────────────
class SignLanguageModule:
    """
    Runs OpenCV + MediaPipe in its own daemon thread.

    Parameters
    ----------
    result_queue : queue.Queue
        Receives TranslationResult objects (mode="sign") when a word/sentence
        is stable enough to emit.
    show_window : bool
        Whether to open a cv2 imshow preview window.
    """

    LABELS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

    def __init__(self, result_queue: queue.Queue, show_window: bool = True):
        self.result_queue    = result_queue
        self.show_window     = show_window
        self.running         = False
        self.last_gesture_time: float = 0.0   # for integrator arbitration

        self._thread: Optional[threading.Thread] = None
        self._model  = _try_load_keras_model(config.SIGN_MODEL_PATH)

        # Setup MediaPipe Tasks Hand Landmarker
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision as mp_vision

        # Try to find hand_landmarker.task in common locations
        task_candidates = [
            "hand_landmarker.task",
            os.path.join(os.path.dirname(__file__), "hand_landmarker.task"),
            os.path.expanduser("~/hand_landmarker.task"),
        ]
        task_path = next((p for p in task_candidates if os.path.exists(p)), None)

        if task_path is None:
            print("[Sign] ⚠  hand_landmarker.task not found. "
                  "Run setup.py or download it manually (see README).")
            print("[Sign] Falling back to legacy MediaPipe Hands API …")
            self._use_tasks_api = False
            self._mp_hands = mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=2,
                min_detection_confidence=0.7,
                min_tracking_confidence=0.7,
            )
            self._detector = None
        else:
            self._use_tasks_api = True
            base_options = mp_python.BaseOptions(model_asset_path=task_path)
            options = mp_vision.HandLandmarkerOptions(
                base_options=base_options,
                num_hands=2,
                min_hand_detection_confidence=0.7,
                min_hand_presence_confidence=0.7,
                min_tracking_confidence=0.7,
            )
            self._detector = mp_vision.HandLandmarker.create_from_options(options)
            self._mp_hands = None
            self._use_tasks_api = True

    # ────────────────────────────────────────────────────────
    # Detection helpers
    # ────────────────────────────────────────────────────────
    def _detect_hands(self, frame: np.ndarray):
        """
        Returns a list of hand landmark lists regardless of which API is used.
        Each landmark is a SimpleNamespace with .x, .y attributes.
        """
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        if self._use_tasks_api and self._detector:
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result   = self._detector.detect(mp_image)
            return result.hand_landmarks  # list of lists of NormalizedLandmark

        elif self._mp_hands:
            # Legacy API
            result = self._mp_hands.process(rgb)
            if result.multi_hand_landmarks:
                return [h.landmark for h in result.multi_hand_landmarks]
        return []

    def _draw_landmarks(self, frame: np.ndarray, hands):
        for hand in hands:
            for lm in hand:
                x = int(lm.x * frame.shape[1])
                y = int(lm.y * frame.shape[0])
                cv2.circle(frame, (x, y), 5, (0, 255, 0), -1)
        return frame

    # ────────────────────────────────────────────────────────
    # Camera loop
    # ────────────────────────────────────────────────────────
    def _run(self):
        cap = cv2.VideoCapture(config.SIGN_CAMERA_INDEX)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  config.SIGN_FRAME_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.SIGN_FRAME_HEIGHT)
        # Request a low-latency buffer
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not cap.isOpened():
            print("[Sign] ❌  Cannot open camera. Sign language module inactive.")
            return

        sentence      = ""
        last_letter   = ""
        frames_stable = 0

        print("[Sign] Camera open. Press 'Q' in the window to stop, 'C' to clear.")

        while self.running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            hands = self._detect_hands(frame)

            if self.show_window:
                frame = self._draw_landmarks(frame, hands)

            letter = ""
            if hands:
                self.last_gesture_time = time.time()
                if self._model is not None:
                    # ── CNN classifier path ──────────────────
                    data = []
                    for lm in hands[0]:
                        data.extend([lm.x, lm.y])
                    arr = np.array(data, dtype=np.float32).reshape(1, -1)
                    if arr.shape[1] == 42:   # 21 landmarks × 2
                        pred = self._model.predict(arr, verbose=0)
                        idx  = np.argmax(pred)
                        if pred[0][idx] > 0.7:
                            letter = self.LABELS[idx] if idx < len(self.LABELS) else ""
                else:
                    # ── Heuristic classifier path ────────────
                    letter = _heuristic_classify(hands)

                # ── Stability smoothing ──────────────────────
                if letter:
                    if letter == last_letter:
                        frames_stable += 1
                    else:
                        last_letter   = letter
                        frames_stable = 0

                    if frames_stable == config.SIGN_STABLE_FRAMES:
                        if letter in ("HELLO", " "):
                            sentence += f" {letter} "
                            frames_stable = -15
                        elif letter == "BACKSPACE":
                            sentence = sentence[:-1]
                            frames_stable = -10
                        else:
                            sentence += letter
                            frames_stable = -config.SIGN_COOLDOWN_FRAMES

                        # Emit result on space / HELLO (word boundary)
                        word = sentence.strip()
                        if word and (letter in (" ", "HELLO") or len(sentence) >= 20):
                            res = TranslationResult(
                                source     = word,
                                translated = word,   # sign → English directly
                                source_lang= "isl",
                                target_lang= config.LANG_ENGLISH,
                                direction  = "sign->en",
                                mode       = "sign",
                                latency_ms = 0.0,
                            )
                            try:
                                self.result_queue.put_nowait(res)
                            except queue.Full:
                                pass
                            sentence = ""

            # ── Overlay HUD ───────────────────────────────────
            if self.show_window:
                h, w = frame.shape[:2]
                overlay = frame.copy()
                cv2.rectangle(overlay, (0, h - 80), (w, h), (0, 0, 0), -1)
                frame = cv2.addWeighted(overlay, 0.6, frame, 0.4, 0)
                cv2.putText(frame, f"Text: {sentence.replace('  ', ' ')}", (20, h - 35),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                if last_letter and 0 <= frames_stable < config.SIGN_STABLE_FRAMES:
                    cv2.putText(frame, f"Detecting: {last_letter} (hold…)", (20, h - 90),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)

                cv2.imshow("Sign Language Detection", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    self.running = False
                    break
                elif key == ord("c"):
                    sentence    = ""
                    last_letter = ""

        cap.release()
        if self.show_window:
            cv2.destroyAllWindows()

    # ────────────────────────────────────────────────────────
    # Public API
    # ────────────────────────────────────────────────────────
    def start(self):
        self.running  = True
        self._thread  = threading.Thread(target=self._run, daemon=True, name="Sign-Worker")
        self._thread.start()
        print(f"[Sign] Started (window={'on' if self.show_window else 'off'}).")

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("[Sign] Stopped.")

    @property
    def is_active(self) -> bool:
        """True if a gesture was seen within the arbitration timeout window."""
        return (time.time() - self.last_gesture_time) < config.SIGN_ACTIVE_TIMEOUT_SEC


# ──────────────────────────────────────────────────────────────
# Standalone test
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    q: queue.Queue = queue.Queue()
    mod = SignLanguageModule(q, show_window=True)
    mod.start()
    print("Running sign language detection. Press Q in window to quit.\n")
    try:
        while mod.running:
            try:
                res = q.get(timeout=1.0)
                print(f"  ✓ Sign: [{res.source}]")
            except queue.Empty:
                pass
    except KeyboardInterrupt:
        mod.stop()
