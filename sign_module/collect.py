# collect.py
# Collect training images from the webcam for each class in labels.json.
#
# Usage:
#   python collect.py
#   python collect.py --camera 1 --size 150

import argparse
import json
import os
import sys

import cv2

from config import CAMERA_INDEX, DATA_DIR, DATASET_SIZE, CAPTURE_DELAY, LABELS_PATH


def collect(camera: int, size: int) -> None:
    if not os.path.exists(LABELS_PATH):
        print(f"[ERROR] labels.json not found at {LABELS_PATH}")
        print('  Create it first, e.g.: {"0": "A", "1": "B", "2": "L"}')
        sys.exit(1)

    with open(LABELS_PATH, "r", encoding="utf-8") as f:
        labels: dict = json.load(f)

    os.makedirs(DATA_DIR, exist_ok=True)

    cap = cv2.VideoCapture(camera)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open camera index {camera}")
        sys.exit(1)

    try:
        for class_idx, class_name in sorted(labels.items(), key=lambda kv: int(kv[0])):
            class_dir = os.path.join(DATA_DIR, class_idx)
            os.makedirs(class_dir, exist_ok=True)

            print(f"\n── Class {class_idx} ({class_name}) ──────────────────────────")
            print("  Position your hand then press Q to start capturing ...")

            while True:
                ret, frame = cap.read()
                if not ret:
                    continue
                cv2.putText(
                    frame,
                    f"Class {class_idx} ({class_name}) - press Q to start",
                    (30, 50),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9, (0, 255, 0), 2, cv2.LINE_AA,
                )
                cv2.imshow("Collect", frame)
                if cv2.waitKey(CAPTURE_DELAY) == ord("q"):
                    break

            counter = 0
            while counter < size:
                ret, frame = cap.read()
                if not ret:
                    continue
                cv2.imshow("Collect", frame)
                cv2.waitKey(CAPTURE_DELAY)
                cv2.imwrite(os.path.join(class_dir, f"{counter}.jpg"), frame)
                counter += 1

            print(f"  Saved {size} images to {class_dir}")

    finally:
        cap.release()
        cv2.destroyAllWindows()

    print("\nCollection complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect sign-language training images.")
    parser.add_argument("--camera", type=int, default=CAMERA_INDEX, help="Camera index (default: 0)")
    parser.add_argument("--size",   type=int, default=DATASET_SIZE,  help="Images per class (default: 100)")
    args = parser.parse_args()
    collect(args.camera, args.size)


if __name__ == "__main__":
    main()
