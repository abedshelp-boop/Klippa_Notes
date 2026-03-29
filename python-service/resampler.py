import io
import numpy as np
import soundfile as sf

from config import SAMPLE_RATE


def audio_to_wav_bytes(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> bytes:
    """Convert a numpy float32 audio array to WAV bytes suitable for the Whisper API."""
    buf = io.BytesIO()
    sf.write(buf, audio, sample_rate, format="WAV", subtype="PCM_16")
    buf.seek(0)
    return buf.read()
