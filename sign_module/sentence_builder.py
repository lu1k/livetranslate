# sentence_builder.py
# Converts a stream of per-frame predictions into a stable sentence.
#
# A character is only appended once it has been the SAME accepted prediction
# for STABILITY_FRAMES consecutive frames.
#
# Special labels:
#   "SPACE"     → appends a space
#   "BACKSPACE" → removes the last character
#   "CLEAR"     → empties the sentence

from typing import Optional

from config import STABILITY_FRAMES


class SentenceBuilder:

    def __init__(self, stability_frames: int = STABILITY_FRAMES) -> None:
        self._stability    = stability_frames
        self._sentence:    list = []
        self._current_char: Optional[str] = None
        self._stable_count: int = 0

    def update(self, character: Optional[str]) -> None:
        """Feed the latest accepted prediction (or None when no hand / low confidence)."""
        if character is None:
            self._reset_counter()
            return

        if character == self._current_char:
            self._stable_count += 1
        else:
            self._current_char = character
            self._stable_count = 1

        if self._stable_count == self._stability:
            self._commit(character)
            self._stable_count = 0   # require another full hold to repeat

    @property
    def sentence(self) -> str:
        return "".join(self._sentence)

    @property
    def stability_progress(self) -> float:
        """0.0 → 1.0 fraction toward committing the current character."""
        if self._stability == 0:
            return 1.0
        return min(self._stable_count / self._stability, 1.0)

    def clear(self) -> None:
        self._sentence.clear()
        self._reset_counter()

    def _commit(self, character: str) -> None:
        upper = character.upper()
        if upper == "BACKSPACE":
            if self._sentence:
                self._sentence.pop()
        elif upper == "CLEAR":
            self._sentence.clear()
        elif upper == "SPACE":
            self._sentence.append(" ")
        else:
            self._sentence.append(character)

    def _reset_counter(self) -> None:
        self._current_char = None
        self._stable_count = 0
