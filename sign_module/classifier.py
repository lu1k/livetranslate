# classifier.py
# Loads the trained model and labels.json, runs predictions.

import json
import os
import pickle
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from config import MODEL_PATH, LABELS_PATH, CONFIDENCE_THRESHOLD


@dataclass
class Prediction:
    character: str
    confidence: float
    accepted: bool          # True when confidence >= CONFIDENCE_THRESHOLD


class SignClassifier:
    """
    Wraps the pickled sklearn model and the runtime-configurable labels map.

    Labels file (labels.json)
    ─────────────────────────
    A JSON object mapping string integer keys to character strings:
        { "0": "A", "1": "B", "2": "L" }

    Add, remove, or rename labels here without touching any other file.
    """

    def __init__(self, model_path: str = MODEL_PATH, labels_path: str = LABELS_PATH) -> None:
        self._model  = self._load_model(model_path)
        self._labels = self._load_labels(labels_path)

    def predict(self, features: List[float]) -> Optional[Prediction]:
        """Run inference on a normalised feature vector."""
        x = np.asarray(features).reshape(1, -1)
        try:
            proba      = self._model.predict_proba(x)[0]
            class_idx  = int(np.argmax(proba))
            confidence = float(proba[class_idx])
            character  = self._labels.get(str(class_idx), f"cls_{class_idx}")
        except Exception as exc:
            raise RuntimeError(f"Prediction failed: {exc}") from exc

        return Prediction(
            character=character,
            confidence=round(confidence, 4),
            accepted=confidence >= CONFIDENCE_THRESHOLD,
        )

    @property
    def labels(self) -> Dict[str, str]:
        return dict(self._labels)

    @staticmethod
    def _load_model(path: str):
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Model not found at {path}. Run train.py first."
            )
        with open(path, "rb") as f:
            return pickle.load(f)["model"]

    @staticmethod
    def _load_labels(path: str) -> Dict[str, str]:
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"labels.json not found at {path}. "
                'Create it first, e.g.: {"0": "A", "1": "B", "2": "L"}'
            )
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
