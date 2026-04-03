import sounddevice as sd
import numpy as np
import queue
import threading

class AudioStream:
    def __init__(
        self,
        sample_rate=44100,
        channels=1,
        dtype='int16',
        blocksize=512,
        target_sample_rate=None,
        processor=None
    ):
        """
        processor: function(audio: np.ndarray, sr: int) -> np.ndarray
        target_sample_rate: resample output to this rate (optional)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype
        self.blocksize = blocksize
        self.target_sample_rate = target_sample_rate
        self.processor = processor

        self._queue = queue.Queue()
        self._running = False
        self._thread = None

    def _callback(self, indata, frames, time, status):
        if status:
            print(status)

        self._queue.put(indata.copy())

    def _resample(self, audio):
        if self.target_sample_rate is None or self.target_sample_rate == self.sample_rate:
            return audio

        # Simple fast resample (linear interpolation)
        ratio = self.target_sample_rate / self.sample_rate
        new_length = int(len(audio) * ratio)

        x_old = np.linspace(0, 1, len(audio))
        x_new = np.linspace(0, 1, new_length)

        return np.interp(x_new, x_old, audio).astype(audio.dtype)

    def _worker(self):
        while self._running:
            data = self._queue.get()

            # Flatten if mono
            if self.channels == 1:
                data = data.flatten()

            # Resample if needed
            data = self._resample(data)

            # Apply user processing
            if self.processor:
                data = self.processor(data, self.target_sample_rate or self.sample_rate)

            # Hook: override this method in usage
            self.on_audio(data)

    def on_audio(self, data):
        """
        Override this OR assign dynamically:
        stream.on_audio = your_function
        """
        pass

    def start(self):
        self._running = True

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype=self.dtype,
            blocksize=self.blocksize,
            callback=self._callback
        )

        self._stream.start()

        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        self._stream.stop()
        self._stream.close()