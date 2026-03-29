import numpy as np
import pyaudiowpatch as pyaudio

from config import (
    SAMPLE_RATE,
    SILENCE_THRESHOLD,
    SILENCE_DURATION_SEC,
    MAX_COMMAND_SEC,
)

_p = pyaudio.PyAudio()

GRACE_PERIOD_SEC = 1.0


def _find_default_mic():
    """Find the default microphone input device."""
    try:
        default = _p.get_default_input_device_info()
        return default
    except OSError:
        for i in range(_p.get_device_count()):
            dev = _p.get_device_info_by_index(i)
            if dev.get("maxInputChannels", 0) > 0 and not dev.get("isLoopbackDevice"):
                return dev
        raise RuntimeError("No microphone found")


def record_command() -> np.ndarray:
    """Record from the microphone until the user stops speaking.

    Stops when silence (RMS below SILENCE_THRESHOLD) persists for
    SILENCE_DURATION_SEC after speech has been detected, or when
    MAX_COMMAND_SEC is reached.
    """
    mic = _find_default_mic()
    mic_rate = int(mic["defaultSampleRate"])
    chunk_size = 1024
    frames: list[np.ndarray] = []

    stream = _p.open(
        format=pyaudio.paFloat32,
        channels=1,
        rate=mic_rate,
        input=True,
        input_device_index=mic["index"],
        frames_per_buffer=chunk_size,
    )

    sec_per_chunk = chunk_size / mic_rate
    silence_chunks_needed = int(SILENCE_DURATION_SEC / sec_per_chunk)
    grace_chunks = int(GRACE_PERIOD_SEC / sec_per_chunk)
    max_chunks = int(MAX_COMMAND_SEC / sec_per_chunk)

    silent_chunks = 0
    speech_started = False
    chunks_read = 0

    try:
        while chunks_read < max_chunks:
            data = stream.read(chunk_size, exception_on_overflow=False)
            chunk = np.frombuffer(data, dtype=np.float32)
            frames.append(chunk)
            chunks_read += 1

            rms = np.sqrt(np.mean(chunk ** 2))

            if rms > SILENCE_THRESHOLD:
                speech_started = True
                silent_chunks = 0
            else:
                silent_chunks += 1

            if speech_started and silent_chunks >= silence_chunks_needed:
                print(f"[Mic] Silence detected after {chunks_read * sec_per_chunk:.1f}s, stopping.")
                break

            if not speech_started and chunks_read > grace_chunks:
                silent_chunks = 0
    finally:
        stream.stop_stream()
        stream.close()

    if not frames:
        return np.array([], dtype=np.float32)

    audio = np.concatenate(frames)

    if mic_rate != SAMPLE_RATE:
        from scipy.signal import resample_poly
        from math import gcd
        g = gcd(mic_rate, SAMPLE_RATE)
        audio = resample_poly(audio, SAMPLE_RATE // g, mic_rate // g).astype(np.float32)

    total_sec = len(audio) / SAMPLE_RATE
    print(f"[Mic] Recorded {total_sec:.1f}s of command audio.")
    return audio
