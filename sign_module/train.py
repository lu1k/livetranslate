# train.py
# Train the RandomForest classifier and save model.p
#
# Usage:
#   python train.py
#   python train.py --test-size 0.25

import argparse
import pickle
import sys

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split

from config import PICKLE_PATH, MODEL_PATH


def train(test_size: float) -> None:
    import os
    if not os.path.exists(PICKLE_PATH):
        print(f"[ERROR] data.pickle not found at {PICKLE_PATH}")
        print("  Run create_dataset.py first.")
        sys.exit(1)

    with open(PICKLE_PATH, "rb") as f:
        data_dict = pickle.load(f)

    # Pad to uniform length (handles any minor landmark count differences)
    raw_data = data_dict["data"]
    max_len  = max(len(s) for s in raw_data)
    data     = np.array([s + [0.0] * (max_len - len(s)) for s in raw_data])
    labels   = np.asarray(data_dict["labels"])

    print(f"  Samples  : {len(data)}")
    print(f"  Classes  : {sorted(set(labels))}")
    print(f"  Features : {data.shape[1]}")

    x_train, x_test, y_train, y_test = train_test_split(
        data, labels,
        test_size=test_size,
        shuffle=True,
        stratify=labels,
        random_state=42,
    )

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(x_train, y_train)

    y_pred = model.predict(x_test)
    acc    = accuracy_score(y_test, y_pred)
    print(f"\n  Test accuracy : {acc * 100:.1f}%")
    print("\n" + classification_report(y_test, y_pred))

    with open(MODEL_PATH, "wb") as f:
        pickle.dump({"model": model}, f)

    print(f"  Model saved to {MODEL_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the sign-language classifier.")
    parser.add_argument("--test-size", type=float, default=0.2, help="Test split fraction (default: 0.2)")
    args = parser.parse_args()
    train(args.test_size)


if __name__ == "__main__":
    main()
