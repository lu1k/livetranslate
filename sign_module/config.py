# config.py
# All tuneable settings live here. Edit this file; nothing else needs changing.

import os

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DATA_DIR    = os.path.join(BASE_DIR, "data")
MODEL_PATH  = os.path.join(BASE_DIR, "model.p")
PICKLE_PATH = os.path.join(BASE_DIR, "data.pickle")
LABELS_PATH = os.path.join(BASE_DIR, "labels.json")

# ── Camera ────────────────────────────────────────────────────────────────────
CAMERA_INDEX  = 0      # change to 1, 2 … if default camera is wrong
DATASET_SIZE  = 100    # images captured per class
CAPTURE_DELAY = 25     # ms between frames during collection

# ── MediaPipe ─────────────────────────────────────────────────────────────────
MIN_DETECTION_CONFIDENCE    = 0.3
STATIC_IMAGE_MODE           = True   # True for dataset creation (still images)
INFERENCE_STATIC_IMAGE_MODE = False  # False for live video (faster tracking)

# ── Classifier ────────────────────────────────────────────────────────────────
CONFIDENCE_THRESHOLD = 0.6   # minimum predict_proba score to accept a prediction

# ── Sentence builder ──────────────────────────────────────────────────────────
STABILITY_FRAMES = 15   # frames a prediction must be stable before it is committed

# ── WebSocket server ──────────────────────────────────────────────────────────
WS_HOST = "0.0.0.0"
WS_PORT = 8765
