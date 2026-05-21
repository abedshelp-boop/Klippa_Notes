from collections import deque

import numpy as np
import pyaudiowpatch as pyaudio

from config import (
    SAMPLE_RATE,
    SILENCE_THRESHOLD,
    SILENCE_DURATION_SEC,
    MAX_COMMAND_SEC,
    NO_SPEECH_TIMEOUT_SEC,
)
from debug import debug

_p = pyaudio.PyAudio()


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


def record_command() -> np.ndarray | None:
    """Record from the microphone until the user stops speaking.

    Behavior:
      - Listens for up to NO_SPEECH_TIMEOUT_SEC for the user to start talking.
        If nothing is heard in that window, returns None to signal "user said
        nothing — abort the whole note instead of capturing dead air".
      - Once speech starts, keeps recording until SILENCE_DURATION_SEC of
        quiet, or until MAX_COMMAND_SEC is reached.
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
    no_speech_timeout_chunks = int(NO_SPEECH_TIMEOUT_SEC / sec_per_chunk)
    max_chunks = int(MAX_COMMAND_SEC / sec_per_chunk)
    # Calibrate ambient noise over ~400ms. Longer than before (was 250ms) so
    # the baseline is more stable — short calibration windows can latch onto
    # a random mic burst or the tail of "Hey Deen" still decaying in the room.
    calibration_chunks = max(1, int(0.4 / sec_per_chunk))
    # Smooth the per-chunk RMS over ~200ms. At 48 kHz + 1024-sample chunks,
    # a single chunk is only ~21 ms — short enough that a single inter-word
    # gap between a stop consonant ("t") and the next vowel reads as silent,
    # which was the visible bug: the listener was cutting people off mid-
    # sentence. Smoothing over ~10 chunks rides through phoneme-scale gaps
    # and only fires "silent" on real end-of-utterance pauses.
    rms_window_size = max(1, int(0.2 / sec_per_chunk))
    rms_window: deque[float] = deque(maxlen=rms_window_size)

    silent_chunks = 0
    speech_started = False
    chunks_read = 0
    calibration_rms: list[float] = []
    start_threshold = SILENCE_THRESHOLD
    # Hysteresis: once speech starts, the bar for "still speaking" drops to
    # 40% of the start threshold. Prevents natural mid-sentence dips from
    # re-registering as silence. A real end-of-command silence drops almost
    # to the ambient floor, well below 0.4× the start threshold.
    continue_threshold = SILENCE_THRESHOLD

    try:
        while chunks_read < max_chunks:
            data = stream.read(chunk_size, exception_on_overflow=False)
            chunk = np.frombuffer(data, dtype=np.float32)
            frames.append(chunk)
            chunks_read += 1

            rms = float(np.sqrt(np.mean(chunk ** 2)))
            rms_window.append(rms)
            smoothed_rms = float(np.mean(rms_window))

            # Calibration phase: learn the noise floor before classifying.
            if chunks_read <= calibration_chunks:
                calibration_rms.append(rms)
                if chunks_read == calibration_chunks:
                    ambient = float(np.mean(calibration_rms))
                    # ambient * 2.0 is less aggressive than the old ambient * 3.0
                    # — normal speech RMS on a laptop mic sits around 0.01-0.03
                    # and the prior 3× multiplier on a slightly-noisy ambient
                    # reading would push the start threshold above the user's
                    # actual speech level.
                    start_threshold = max(SILENCE_THRESHOLD, ambient * 2.0)
                    continue_threshold = max(SILENCE_THRESHOLD * 0.5,
                                             start_threshold * 0.4)
                    debug.log(
                        "Mic",
                        "calibrated",
                        {
                            "ambient": ambient,
                            "start_threshold": start_threshold,
                            "continue_threshold": continue_threshold,
                        },
                    )
                continue

            # Choose threshold based on whether speech has already started —
            # this is the hysteresis step. Before speech: strict. During
            # speech: permissive, so mid-word dips don't count as silence.
            active_threshold = continue_threshold if speech_started else start_threshold

            if smoothed_rms > active_threshold:
                if not speech_started:
                    speech_started = True
                    debug.log(
                        "Mic",
                        "speech detected",
                        {"at_sec": chunks_read * sec_per_chunk},
                    )
                silent_chunks = 0
            else:
                silent_chunks += 1

            # Stop case 1: speech happened, then went quiet for SILENCE_DURATION_SEC.
            if speech_started and silent_chunks >= silence_chunks_needed:
                debug.log(
                    "Mic",
                    "silence after speech — stopping",
                    {
                        "silence_sec": SILENCE_DURATION_SEC,
                        "elapsed_sec": chunks_read * sec_per_chunk,
                    },
                )
                break

            # Stop case 2: nothing was ever said. Abort the whole note.
            if not speech_started and chunks_read >= no_speech_timeout_chunks:
                debug.warn(
                    "Mic",
                    "no speech — aborting note",
                    {"timeout_sec": NO_SPEECH_TIMEOUT_SEC},
                )
                return None
    finally:
        stream.stop_stream()
        stream.close()

    if not frames:
        return None

    audio = np.concatenate(frames)

    if mic_rate != SAMPLE_RATE:
        from scipy.signal import resample_poly
        from math import gcd
        g = gcd(mic_rate, SAMPLE_RATE)
        audio = resample_poly(audio, SAMPLE_RATE // g, mic_rate // g).astype(np.float32)

    total_sec = len(audio) / SAMPLE_RATE
    debug.log("Mic", "recorded command audio", {"total_sec": total_sec})
    return audio
