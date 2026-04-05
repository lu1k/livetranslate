"""
isl.py — Your ISL (Indian Sign Language) script
=================================================
vaani_server.py spawns this file as a subprocess and reads its stdout.

CONTRACT: print one sign per line, pipe-separated, flushed immediately.

    print("WORD|Description of the ISL gesture", flush=True)

Examples of valid output lines:
    HELLO|Right hand raised to forehead level, palm outward, sweeps forward.
    WATER|Both hands form a W shape and tap the chin twice.
    PLEASE|Right hand flat against chest, moves in a circular motion.
    THANK YOU|Right hand touches lips then moves forward, palm facing up.

The part before the pipe  →  shown as the sign label  (cyan, left column)
The part after  the pipe  →  shown as the description  (right column)

If you print plain text with no pipe, the whole line becomes the
description and the label column is left empty — also works fine.

─────────────────────────────────────────────────────────────────────────
HOW TO ADAPT YOUR EXISTING SCRIPT
─────────────────────────────────────────────────────────────────────────
Your script likely already has something like:

    # existing code
    sign_label   = "HELLO"
    sign_gesture = "Right hand raised to forehead..."
    print(sign_gesture)          # ← old print

Change it to:

    print(f"{sign_label}|{sign_gesture}", flush=True)   # ← new print

That's the only change needed.
─────────────────────────────────────────────────────────────────────────

Below is a minimal working example that simulates ISL output so you
can test the pipeline before plugging in your real model.
"""

import sys
import time
import random

# ── Demo signs dictionary ──────────────────────────────────────────────────────
# Replace this with your actual ISL model / detection logic.

DEMO_SIGNS = [
    ("HELLO",    "Right hand raised to forehead level, palm outward, sweeps forward and down."),
    ("THANK YOU","Right hand touches lips then moves forward, palm facing up."),
    ("WATER",    "Both hands form a W shape and tap the chin twice."),
    ("PLEASE",   "Right hand flat against chest, moves in a slow circular motion."),
    ("SORRY",    "Right hand closed fist placed on chest and moves in a circular motion."),
    ("YES",      "Right hand closed fist nods up and down at the wrist."),
    ("NO",       "Index and middle fingers tap the thumb twice."),
    ("HELP",     "Right fist placed on left open palm; both hands move upward together."),
    ("FOOD",     "Fingertips of right hand tap lips twice."),
    ("HOME",     "Fingertips touch lips then the cheek in sequence."),
]


def main():
    print("[ISL] Starting — replace this demo with your real model", file=sys.stderr, flush=True)

    # ── Replace everything below with your real ISL detection loop ────────────
    #
    # Example structure for a camera-based model:
    #
    #   import cv2, your_isl_model
    #   cap = cv2.VideoCapture(0)
    #   while True:
    #       ret, frame = cap.read()
    #       sign_label, description = your_isl_model.predict(frame)
    #       if sign_label:
    #           print(f"{sign_label}|{description}", flush=True)
    #
    # ─────────────────────────────────────────────────────────────────────────

    # Demo: emit a random sign every 2-4 seconds
    while True:
        word, description = random.choice(DEMO_SIGNS)

        # ── THIS IS THE IMPORTANT LINE ────────────────────────────────────────
        # Print WORD|Description, one per line, flushed immediately.
        # vaani_server.py reads this and sends it to the Electron frontend.
        print(f"{word}|{description}", flush=True)
        # ─────────────────────────────────────────────────────────────────────

        time.sleep(random.uniform(2.0, 4.0))


if __name__ == "__main__":
    main()
