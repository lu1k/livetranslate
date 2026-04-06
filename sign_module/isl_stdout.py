# isl_stdout.py
# Runs the sign-language inference loop and prints results to stdout
# so vaani_server.py can read them line by line.
#
# Output format (pipe-separated, one line per committed character):
#   WORD|Sentence so far
#   e.g.  A|A
#         B|AB
#
# vaani_server.py reads this via ManagedProcess and forwards it to the frontend.
# No WebSocket needed here — stdout is the transport.

import sys

import cv2

from classifier import SignClassifier
from config import CAMERA_INDEX
from hand_tracker import HandTracker
from sentence_builder import SentenceBuilder
print("ISL SCRIPT STARTED", flush=True)

def main() -> None:
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("ERROR|Cannot open camera", flush=True)
        sys.exit(1)

    try:
        classifier = SignClassifier()
    except FileNotFoundError as exc:
        print(f"ERROR|{exc}", flush=True)
        sys.exit(1)

    tracker  = HandTracker()
    builder  = SentenceBuilder()
    last_sentence = ""

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                continue

            tracking = tracker.process(frame)

            if tracking.hand_detected and tracking.features is not None:
                pred = classifier.predict(tracking.features)
                if pred and pred.accepted:
                    builder.update(pred.character)
                else:
                    builder.update(None)
            else:
                builder.update(None)

            current = builder.sentence
            if current != last_sentence and current:
                last_char = current[-1]
                description = f"Current sentence: {current}"
                print(f"{last_char}|{description}", flush=True)
                last_sentence = current

    finally:
        tracker.close()
        cap.release()


if __name__ == "__main__":
    main()
