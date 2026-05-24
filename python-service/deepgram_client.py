"""
Deepgram Nova-3 transcription wrapper.

The wake-word and push-to-talk pipelines both arrive with a complete WAV blob
in memory, so we use the pre-recorded ("media") endpoint rather than the
streaming WebSocket. Nova-3 is the same model the streaming endpoint uses —
the picking of "streaming" in the spec referred to the model family, not the
transport. If we later wire a live in-canvas dictation surface, we can swap
to `client.listen.v1.connect(model="nova-3")` without callers noticing.

Failures (no key, network down, 4xx/5xx) raise `DeepgramUnavailable` so the
chain in `ai_client._chained_transcribe()` can fall back to faster-whisper
deterministically.
"""
from __future__ import annotations

from typing import Optional

from debug import debug


class DeepgramUnavailable(RuntimeError):
    """Raised when Deepgram can't fulfil the request — caller falls back."""


_client = None
_configured_key: Optional[str] = None


def _get_client():
    """Lazy-init a single DeepgramClient. Re-created when the key rotates so
    runtime settings updates take effect without restarting the service."""
    global _client, _configured_key
    # Read inside the function so test code that monkeypatches config.DEEPGRAM_API_KEY
    # post-import still works.
    import config  # noqa: WPS433 — runtime import is intentional
    key = (config.DEEPGRAM_API_KEY or "").strip()
    if not key:
        raise DeepgramUnavailable("DEEPGRAM_API_KEY is not set")

    if _client is None or _configured_key != key:
        try:
            from deepgram import DeepgramClient  # type: ignore[import-not-found]
        except ImportError as e:
            raise DeepgramUnavailable(
                "deepgram-sdk not installed; pip install deepgram-sdk>=5.0.0"
            ) from e
        _client = DeepgramClient(api_key=key)
        _configured_key = key
    return _client


def transcribe_with_deepgram(
    wav_bytes: bytes,
    with_speakers: bool = False,
    language_hint: Optional[str] = None,
) -> str:
    """Synchronously transcribe a WAV blob with Deepgram Nova-3.

    Args:
        wav_bytes: a complete WAV payload (mono PCM16 preferred but Deepgram
                   accepts other containers).
        with_speakers: enable diarization. When True, the returned string is
                       speaker-labelled (``"[Speaker 0]: ...\\n[Speaker 1]: ..."``)
                       so the existing LLM prompt can attribute utterances.
        language_hint: optional ISO-639-1 code. ``None`` lets Deepgram auto-detect,
                       which is the right default for the polyglot system audio.

    Returns:
        A plain transcript string. Empty string means Deepgram returned a
        success response with no speech; caller decides whether to treat that
        as "user said nothing".

    Raises:
        DeepgramUnavailable: anything that should trigger fallback — missing
        key, missing SDK, network failure, Deepgram API error, surprise
        response shape. The chain never crashes on these.
    """
    if not wav_bytes:
        return ""

    client = _get_client()

    try:
        # Import-locally so a missing SDK only blows up the path that needs it,
        # not the whole service startup.
        from deepgram.core.api_error import ApiError  # type: ignore[import-not-found]
    except ImportError:  # SDK present but layout differs — treat as unavailable.
        raise DeepgramUnavailable("deepgram-sdk ApiError import failed")

    kwargs = {
        "model": "nova-3",
        "smart_format": True,
        "punctuate": True,
    }
    if with_speakers:
        kwargs["diarize"] = True
    if language_hint:
        kwargs["language"] = language_hint

    try:
        response = client.listen.v1.media.transcribe_file(
            request=wav_bytes, **kwargs,
        )
    except ApiError as e:
        raise DeepgramUnavailable(
            f"Deepgram API error: status={getattr(e, 'status_code', '?')}"
        ) from e
    except Exception as e:  # noqa: BLE001 — network/transport/etc all funnel here
        raise DeepgramUnavailable(f"Deepgram call failed: {e}") from e

    text = _extract_transcript(response, with_speakers=with_speakers)
    debug.log(
        "Deepgram",
        "transcribed",
        {
            "chars": len(text),
            "with_speakers": with_speakers,
            "lang_hint": language_hint or "auto",
        },
    )
    return text


def _extract_transcript(response, with_speakers: bool) -> str:
    """Pull the transcript text (with speaker labels when requested) out of
    the SDK response object. Tolerant of small response-shape differences
    between SDK minor versions — anything unexpected raises DeepgramUnavailable
    so the caller falls back rather than corrupting downstream state."""
    try:
        channel = response.results.channels[0]
        alternative = channel.alternatives[0]
    except (AttributeError, IndexError) as e:
        raise DeepgramUnavailable(f"Unexpected response shape: {e}") from e

    if not with_speakers:
        return (getattr(alternative, "transcript", "") or "").strip()

    words = getattr(alternative, "words", None) or []
    if not words:
        # Diarize enabled but no words — fall through to the plain transcript
        # so we still return something useful.
        return (getattr(alternative, "transcript", "") or "").strip()

    lines: list[str] = []
    current_speaker = None
    current_words: list[str] = []
    for w in words:
        speaker = getattr(w, "speaker", None)
        text = getattr(w, "punctuated_word", None) or getattr(w, "word", "") or ""
        if speaker != current_speaker:
            if current_words:
                lines.append(
                    f"[Speaker {current_speaker}]: {' '.join(current_words).strip()}"
                )
            current_speaker = speaker
            current_words = [text]
        else:
            current_words.append(text)
    if current_words:
        lines.append(
            f"[Speaker {current_speaker}]: {' '.join(current_words).strip()}"
        )
    return "\n".join(lines).strip()
