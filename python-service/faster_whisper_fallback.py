"""
Offline / Deepgram-unreachable fallback transcriber using faster-whisper.

The Deepgram chain is the default; this kicks in when Deepgram raises
``DeepgramUnavailable`` (no key, network down, API error). Whisper-small on
CPU with int8 quantization is the sweet spot for a desktop fallback —
~480 MB model, ~3× faster than openai-whisper at similar accuracy, no GPU
needed. The first call after process boot pays a one-time model-load cost
(~2-4 s on a modest laptop); subsequent calls are sub-second on short clips.

Like the Deepgram wrapper, anything that can't return a transcript raises
``WhisperUnavailable`` so callers can decide on the next fallback rather
than receiving an empty string and silently dropping a capture.
"""
from __future__ import annotations

import io
import os
import threading
from typing import Optional

from debug import debug


class WhisperUnavailable(RuntimeError):
    """Raised when faster-whisper can't transcribe — caller falls back."""


_model = None
_model_lock = threading.Lock()
# Small is the right default for a fallback: large enough for English +
# Arabic dictation, small enough that the first download (~480 MB) doesn't
# strand a user on a slow connection. Override via FASTER_WHISPER_MODEL_SIZE.
_MODEL_SIZE_ENV = "FASTER_WHISPER_MODEL_SIZE"
_DEFAULT_MODEL_SIZE = "small"


def _get_model():
    """Lazy-load WhisperModel under a lock so concurrent first-callers don't
    each download/load the model independently. Subsequent calls hit the
    cached singleton."""
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        try:
            from faster_whisper import WhisperModel  # type: ignore[import-not-found]
        except ImportError as e:
            raise WhisperUnavailable(
                "faster-whisper not installed; pip install faster-whisper"
            ) from e
        size = os.getenv(_MODEL_SIZE_ENV, _DEFAULT_MODEL_SIZE)
        debug.log("Whisper", "loading model", {"size": size, "device": "cpu"})
        try:
            _model = WhisperModel(size, device="cpu", compute_type="int8")
        except Exception as e:  # noqa: BLE001 — model download / CTranslate2 / disk
            raise WhisperUnavailable(f"faster-whisper init failed: {e}") from e
        debug.log("Whisper", "model loaded", {"size": size})
        return _model


def transcribe_with_local_whisper(
    wav_bytes: bytes,
    language_hint: Optional[str] = None,
) -> str:
    """Synchronously transcribe a WAV blob with faster-whisper on CPU.

    Args:
        wav_bytes: a complete WAV payload (PCM16 mono preferred).
        language_hint: optional ISO-639-1 code. ``None`` triggers
                       auto-detection — works fine for English / Arabic.

    Returns:
        The concatenated transcript as a single string (no speaker labels —
        faster-whisper doesn't diarize). Empty string means VAD or model
        produced no segments.

    Raises:
        WhisperUnavailable: model can't load, decode fails, or audio is
        unreadable. Caller decides next fallback.
    """
    if not wav_bytes:
        return ""

    model = _get_model()

    # faster-whisper accepts file-like objects directly — no need to write to
    # a tempfile. BytesIO is read by ctranslate2 / soundfile under the hood.
    audio = io.BytesIO(wav_bytes)
    audio.name = "audio.wav"

    try:
        segments, info = model.transcribe(
            audio,
            beam_size=5,
            language=language_hint,
            vad_filter=False,  # upstream VAD already trimmed silence
        )
        # Force generator evaluation here so we can raise inside this try.
        texts = [(s.text or "").strip() for s in segments]
    except Exception as e:  # noqa: BLE001
        raise WhisperUnavailable(f"faster-whisper transcribe failed: {e}") from e

    transcript = " ".join(t for t in texts if t).strip()
    debug.log(
        "Whisper",
        "transcribed",
        {
            "chars": len(transcript),
            "lang": getattr(info, "language", None),
            "lang_prob": round(getattr(info, "language_probability", 0.0), 2),
        },
    )
    return transcript
