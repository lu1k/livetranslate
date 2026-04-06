# hand_tracker.py
# Wraps MediaPipe Hands and returns clean tracking results.

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import cv2
import mediapipe as mp
import numpy as np

from config import MIN_DETECTION_CONFIDENCE, INFERENCE_STATIC_IMAGE_MODE


@dataclass
class TrackingResult:
    landmarks: List[List[Tuple[float, float]]] = field(default_factory=list)
    features: Optional[List[float]] = None
    annotated: Optional[np.ndarray] = None
    hand_detected: bool = False


class HandTracker:
    """
    Reusable MediaPipe hand tracker.

    Parameters
    ----------
    static_image_mode : bool
        True  → each frame is independent (good for dataset creation).
        False → tracking mode, lower latency for live video.
    """

    def __init__(self, static_image_mode: bool = INFERENCE_STATIC_IMAGE_MODE) -> None:
        self._mp_hands   = mp.solutions.hands
        self._mp_drawing = mp.solutions.drawing_utils
        self._mp_styles  = mp.solutions.drawing_styles

        self._hands = self._mp_hands.Hands(
            static_image_mode=static_image_mode,
            min_detection_confidence=MIN_DETECTION_CONFIDENCE,
        )

    def process(self, bgr_frame: np.ndarray) -> TrackingResult:
        """Run hand detection on a single BGR frame."""
        result = TrackingResult(annotated=bgr_frame.copy())
        rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        mp_result = self._hands.process(rgb_frame)

        if not mp_result.multi_hand_landmarks:
            return result

        result.hand_detected = True

        # Draw skeleton overlay on annotated frame
        for hand_lm in mp_result.multi_hand_landmarks:
            self._mp_drawing.draw_landmarks(
                result.annotated,
                hand_lm,
                self._mp_hands.HAND_CONNECTIONS,
                self._mp_styles.get_default_hand_landmarks_style(),
                self._mp_styles.get_default_hand_connections_style(),
            )

        # Collect raw (x, y) pairs per hand
        for hand_lm in mp_result.multi_hand_landmarks:
            result.landmarks.append([(lm.x, lm.y) for lm in hand_lm.landmark])

        # Build normalised feature vector from the first hand only
        first = mp_result.multi_hand_landmarks[0]
        xs = [lm.x for lm in first.landmark]
        ys = [lm.y for lm in first.landmark]
        min_x, min_y = min(xs), min(ys)

        features: List[float] = []
        for lm in first.landmark:
            features.append(lm.x - min_x)
            features.append(lm.y - min_y)

        result.features = features
        return result

    def close(self) -> None:
        self._hands.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
