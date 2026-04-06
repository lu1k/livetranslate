# create_dataset.py
# Process collected images through MediaPipe and save feature vectors.
#
# Usage:
#   python create_dataset.py

import os
import pickle
import sys

import cv2

from config import DATA_DIR, PICKLE_PATH
from hand_tracker import HandTracker


def create_dataset() -> None:
    if not os.path.exists(DATA_DIR):
        print(f"[ERROR] Data directory not found: {DATA_DIR}")
        print("  Run collect.py first.")
        sys.exit(1)

    class_dirs = sorted(
        [d for d in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, d))],
        key=lambda x: int(x) if x.isdigit() else x
    )

    if not class_dirs:
        print("[ERROR] No class sub-directories found in data/")
        sys.exit(1)

    data:    list = []
    labels:  list = []
    skipped: int  = 0

    # static_image_mode=True because each image is independent
    with HandTracker(static_image_mode=True) as tracker:
        for class_label in class_dirs:
            class_path = os.path.join(DATA_DIR, class_label)
            images = [
                f for f in os.listdir(class_path)
                if f.lower().endswith((".jpg", ".jpeg", ".png"))
            ]
            print(f"  Processing class {class_label}: {len(images)} images ...")

            for img_file in images:
                img_path = os.path.join(class_path, img_file)
                frame = cv2.imread(img_path)
                if frame is None:
                    skipped += 1
                    continue

                result = tracker.process(frame)
                if result.features is None:
                    skipped += 1
                    continue

                data.append(result.features)
                labels.append(class_label)

    print(f"\n  Total samples : {len(data)}")
    print(f"  Skipped       : {skipped}  (no hand detected)")

    with open(PICKLE_PATH, "wb") as f:
        pickle.dump({"data": data, "labels": labels}, f)

    print(f"  Dataset saved to {PICKLE_PATH}")


if __name__ == "__main__":
    create_dataset()
