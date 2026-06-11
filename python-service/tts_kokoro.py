"""
Local Kokoro TTS for hear-back confirmations.

We use `kokoro-onnx` (not the PyTorch-flavoured `kokoro` package): smaller
install, runs on CPU at sub-second latency for short phrases like "Saved to
<note>", no torch dependency to pin on Python 3.14. The model + voices files
ship next to the service (see config.KOKORO_MODEL_PATH /
config.KOKORO_VOICES_PATH) and are downloaded out-of-band — they're large
binaries, not appropriate for git.

Failure modes (model file missing, SDK missing, voice not in the pack) raise
``TTSUnavailable`` so the FastAPI route can return a 503 and the renderer
can treat hear-back as best-effort.
"""
from __future__ import annotations

import io
import threading
from pathlib import Path
from typing import Optional

from debug import debug

# Kokoro-ONNX returns float32 samples at this rate. Hard-coded by the model.
_KOKORO_SAMPLE_RATE = 24000


class TTSUnavailable(RuntimeError):
    """Raised when Kokoro can't synthesize — caller decides UX (503, no-op)."""


_kokoro = None
_kokoro_lock = threading.Lock()
_configured_paths: tuple[str, str] | None = None


def _get_kokoro():
    """Lazy-load a single Kokoro instance under a lock. Re-created when the
    configured model/voices paths change so config-overrides take effect
    without restarting the service."""
    global _kokoro, _configured_paths
    # Read config inside the function so tests can monkeypatch paths post-import.
    import config  # noqa: WPS433
    model_path = str(config.KOKORO_MODEL_PATH or "").strip()
    voices_path = str(config.KOKORO_VOICES_PATH or "").strip()
    if not model_path or not voices_path:
        raise TTSUnavailable("KOKORO_MODEL_PATH / KOKORO_VOICES_PATH not set")

    if not Path(model_path).exists():
        raise TTSUnavailable(f"Kokoro model file not found: {model_path}")
    if not Path(voices_path).exists():
        raise TTSUnavailable(f"Kokoro voices file not found: {voices_path}")

    with _kokoro_lock:
        paths = (model_path, voices_path)
        if _kokoro is not None and _configured_paths == paths:
            return _kokoro
        try:
            from kokoro_onnx import Kokoro  # type: ignore[import-not-found]
        except ImportError as e:
            raise TTSUnavailable(
                "kokoro-onnx not installed; pip install kokoro-onnx"
            ) from e
        try:
            debug.log("Kokoro", "loading model", {"model": model_path})
            _kokoro = Kokoro(model_path, voices_path)
            _configured_paths = paths
            debug.log("Kokoro", "model loaded")
        except Exception as e:  # noqa: BLE001 — onnx-runtime / bad file / etc.
            raise TTSUnavailable(f"Kokoro init failed: {e}") from e
        return _kokoro


def synthesize_to_wav(
    text: str,
    voice: Optional[str] = None,
    speed: float = 1.05,
) -> bytes:
    """Render text to a 16-bit PCM WAV blob using Kokoro.

    Args:
        text:  the sentence to speak. Empty or whitespace returns b"" with no
               model invocation — the route turns that into a 0-byte WAV.
        voice: voice id (e.g. "af_heart"). ``None`` uses config.KOKORO_VOICE
               which defaults to the warm female voice the spec asked for.
        speed: 1.0 is neutral. 1.05 sounds a touch livelier without losing
               clarity on short confirmation phrases.

    Returns:
        Bytes of a complete WAV file (RIFF header + PCM_16 samples at 24 kHz).

    Raises:
        TTSUnavailable: anything that prevents synthesis (missing model
        files, missing SDK, runtime error, unknown voice).
    """
    phrase = (text or "").strip()
    if not phrase:
        return b""

    import config  # noqa: WPS433
    voice_id = (voice or config.KOKORO_VOICE or "af_heart").strip()

    kokoro = _get_kokoro()

    try:
        samples, sample_rate = kokoro.create(
            phrase, voice=voice_id, speed=speed, lang="en-us",
        )
    except Exception as e:  # noqa: BLE001 — voice missing, onnx blow-up, etc.
        raise TTSUnavailable(f"Kokoro synthesis failed: {e}") from e

    if samples is None or len(samples) == 0:
        return b""

    # Encode in-memory to avoid a tempfile on the hot path.
    import soundfile as sf  # local import keeps the cold-start light

    buf = io.BytesIO()
    try:
        sf.write(buf, samples, sample_rate, format="WAV", subtype="PCM_16")
    except Exception as e:  # noqa: BLE001
        raise TTSUnavailable(f"WAV encoding failed: {e}") from e

    wav = buf.getvalue()
    debug.log(
        "Kokoro",
        "synthesized",
        {"chars": len(phrase), "bytes": len(wav), "voice": voice_id},
    )
    return wav
