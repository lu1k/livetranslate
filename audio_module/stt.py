import numpy as np
from faster_whisper import WhisperModel
import threading
import queue
from audio_module.audio_mod import AudioStream


class MalayalamTranscriber:
    def __init__(
        self,
        model_size="medium",
        sample_rate=16000,
        silence_threshold=100,
        silence_duration=0.5,
        min_speech_duration=0.6,
        on_transcript=None
    ):
        """
        model_size: whisper model — "tiny", "small", "medium", "large"
        sample_rate: must be 16000 for Whisper
        silence_threshold: RMS amplitude below which audio is considered silence
        silence_duration: seconds of silence to trigger transcription
        min_speech_duration: minimum seconds of speech before transcribing
        on_transcript: callback(text: str) called with each translated result
        """
        self.sample_rate = sample_rate
        self.silence_threshold = silence_threshold
        self.silence_frames = int(silence_duration * sample_rate)
        self.min_speech_frames = int(min_speech_duration * sample_rate)
        self.on_transcript = on_transcript

        print(f"Loading Whisper '{model_size}' model...")
        self.model = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8")

        print("Model loaded.")

        self._audio_buffer = []
        self._silence_counter = 0
        self._processing_queue = queue.Queue()
        self._running = False

        self.stream = AudioStream(
            sample_rate=sample_rate,
            channels=1,
            dtype='int16',
            blocksize=2048,
            target_sample_rate=sample_rate,
        )
        self.stream.on_audio = self._on_audio_chunk

    def _is_silent(self, chunk: np.ndarray) -> bool:
        rms = np.sqrt(np.mean(chunk.astype(np.float32) ** 2))
        return rms < self.silence_threshold

    def _on_audio_chunk(self, chunk: np.ndarray, *_):
        
        """Accumulate audio and flush on sustained silence."""
        if self._is_silent(chunk):
            self._silence_counter += len(chunk)

            # Still accumulate a bit during silence for natural sentence endings
            if self._silence_counter <= self.silence_frames:
                self._audio_buffer.append(chunk)

            # Flush buffer once silence threshold is exceeded
            elif len(self._audio_buffer) > 0:
                total_frames = sum(len(c) for c in self._audio_buffer)
                if total_frames >= self.min_speech_frames:
                    audio = np.concatenate(self._audio_buffer)
                    self._processing_queue.put(audio)
                self._audio_buffer = []
                self._silence_counter = 0
        else:
            self._silence_counter = 0
            self._audio_buffer.append(chunk)

    def _transcribe_worker(self):
        """Background thread: transcribes and translates queued audio segments."""
        while self._running:
            try:
                audio = self._processing_queue.get()
                print("Processing speech...")
            except queue.Empty:
                continue

            try:
                # Whisper expects float32 in [-1.0, 1.0]
                audio_float = audio.astype(np.float32) / 32768.0
                max_val = np.max(np.abs(audio_float))
                if max_val > 0:
                    audio_float = audio_float / max_val

                segments, info = self.model.transcribe(
                    audio_float,
                    language="ml",       # Malayalam
                    task="translate",    # Translate directly to English
                    beam_size=5)
                
                text = " ".join([seg.text for seg in segments]).strip()
                
                
                if text and self.on_transcript:
                    self.on_transcript(text)

            except Exception as e:
                print(f"Transcription error: {e}")

    def start(self):
        self._running = True
        self._worker_thread = threading.Thread(
            target=self._transcribe_worker,
            daemon=True
        )
        self._worker_thread.start()
        self.stream.start()
        print("Listening... (speak in Malayalam)")

    def stop(self):
        self._running = False
        self.stream.stop()
        self._worker_thread.join(timeout=2.0)
        print("Stopped.")
def handle_transcript(text: str):
    # Send transcript to vaani_server.py
    print("Translated:",text)


if __name__ == "__main__":
    transcriber = MalayalamTranscriber(
        model_size="medium",
        on_transcript=handle_transcript
    )

    try:
        transcriber.start()

        import time
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        transcriber.stop()
