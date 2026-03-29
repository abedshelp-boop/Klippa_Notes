import threading
import numpy as np
from config import SAMPLE_RATE, BUFFER_DURATION_SEC


class RingBuffer:
    """Thread-safe rolling audio buffer that stores the last N seconds of audio."""

    def __init__(self, duration_sec=BUFFER_DURATION_SEC, sample_rate=SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.max_samples = duration_sec * sample_rate
        self._buffer = np.zeros(self.max_samples, dtype=np.float32)
        self._write_pos = 0
        self._total_written = 0
        self._lock = threading.Lock()

    def write(self, audio_chunk: np.ndarray):
        chunk = audio_chunk.astype(np.float32).flatten()
        n = len(chunk)
        with self._lock:
            if n >= self.max_samples:
                self._buffer[:] = chunk[-self.max_samples:]
                self._write_pos = 0
                self._total_written += n
                return

            end = self._write_pos + n
            if end <= self.max_samples:
                self._buffer[self._write_pos:end] = chunk
            else:
                first = self.max_samples - self._write_pos
                self._buffer[self._write_pos:] = chunk[:first]
                self._buffer[:n - first] = chunk[first:]

            self._write_pos = end % self.max_samples
            self._total_written += n

    def read_last(self, duration_sec: float) -> np.ndarray:
        n_samples = int(duration_sec * self.sample_rate)
        with self._lock:
            available = min(self._total_written, self.max_samples)
            n_samples = min(n_samples, available)
            if n_samples == 0:
                return np.zeros(0, dtype=np.float32)

            start = (self._write_pos - n_samples) % self.max_samples
            if start < self._write_pos:
                return self._buffer[start:self._write_pos].copy()
            else:
                return np.concatenate([
                    self._buffer[start:],
                    self._buffer[:self._write_pos],
                ]).copy()
