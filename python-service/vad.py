"""
Voice Activity Detection via Silero-VAD.

Trims silence and non-speech audio from the system audio clip before it
reaches the transcriber. OpenAI Whisper and gpt-4o-mini-transcribe are
notorious for hallucinating religious content ("And the one who believed
said, O my people...", "Subscribe to my channel", etc.) when fed silence
or quiet non-speech audio — those phrases are over-represented in training
data. Eliminating silence at the input kills the hallucination at its root.

Uses the ONNX path (load_silero_vad(onnx=True)) — keeps inference on
onnxruntime, which the project already ships for openwakeword. Torch is
still imported because Silero's `get_speech_timestamps` takes a torch.Tensor,
but inference itself runs through onnxruntime.

Public:
    extract_speech(audio, sample_rate) -> np.ndarray
"""
from __future__ import annotations

import numpy as np
import torch

from silero_vad import load_silero_vad, get_speech_timestamps

from config import (
    VAD_MAX_SPEECH_SEC,
    VAD_MIN_SPEECH_MS,
    VAD_MIN_SILENCE_MS,
    VAD_SPEECH_PAD_MS,
    VAD_THRESHOLD,
)
from debug import debug


# Lazy model handle. load_silero_vad() caches the model file in the Silero
# package dir on first call; subsequent calls reuse the in-memory instance.
_model = None


def _get_model():
    global _model
    if _model is None:
        _model = load_silero_vad(onnx=True)
    return _model


def extract_speech(
    audio: np.ndarray,
    sample_rate: int,
    max_speech_sec: int = VAD_MAX_SPEECH_SEC,
) -> np.ndarray:
    """Run Silero-VAD on `audio`, concatenate all detected speech segments
    (dropping silence between them), and return the most recent
    `max_speech_sec` seconds of speech.

    Returns an empty np.ndarray if no speech is detected.

    Args:
        audio: float32 mono audio in [-1, 1]. Any sample rate supported by
            Silero (8 kHz or 16 kHz); anything else bypasses VAD.
        sample_rate: Must be 8000 or 16000 — Silero-VAD constraint.
        max_speech_sec: Cap on total speech-seconds returned. Oldest speech
            is dropped first when we exceed the budget.
    """
    if audio is None or len(audio) == 0:
        return np.zeros(0, dtype=np.float32)

    if sample_rate not in (8000, 16000):
        # Shouldn't happen — our pipeline is locked to 16 kHz — but bail
        # safely rather than silently corrupting audio.
        debug.warn(
            "VAD",
            "unsupported sample_rate, returning audio unchanged",
            {"sample_rate": sample_rate},
        )
        return audio

    model = _get_model()
    audio_tensor = torch.from_numpy(np.ascontiguousarray(audio, dtype=np.float32))

    segments = get_speech_timestamps(
        audio_tensor,
        model,
        sampling_rate=sample_rate,
        threshold=VAD_THRESHOLD,
        min_speech_duration_ms=VAD_MIN_SPEECH_MS,
        min_silence_duration_ms=VAD_MIN_SILENCE_MS,
        speech_pad_ms=VAD_SPEECH_PAD_MS,
        return_seconds=False,
    )

    total_sec = len(audio) / sample_rate
    if not segments:
        debug.log("VAD", "no speech detected", {"total_sec": total_sec})
        return np.zeros(0, dtype=np.float32)

    speech = np.concatenate(
        [audio[seg["start"]:seg["end"]] for seg in segments]
    ).astype(np.float32)

    max_samples = int(max_speech_sec * sample_rate)
    truncated = False
    if len(speech) > max_samples:
        speech = speech[-max_samples:]
        truncated = True

    speech_sec = len(speech) / sample_rate
    pct = (speech_sec / total_sec * 100.0) if total_sec > 0 else 0.0
    debug.log(
        "VAD",
        "speech segments kept",
        {
            "segments": len(segments),
            "kept_sec": speech_sec,
            "total_sec": total_sec,
            "pct": pct,
            "truncated": truncated,
        },
    )
    return speech
