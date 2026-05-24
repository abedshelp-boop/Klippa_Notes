"""Integration tests for ai_client.transcribe_audio()'s tier chain.

Covers the contract: Deepgram → faster-whisper → legacy.
Each tier is mocked so no network or model load happens.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

import ai_client
from deepgram_client import DeepgramUnavailable
from faster_whisper_fallback import WhisperUnavailable


@pytest.fixture
def patched_chain():
    """Patch all three tiers so each test can wire the outcomes it needs."""
    with patch.object(ai_client, "transcribe_with_deepgram") as dg, \
         patch.object(ai_client, "transcribe_with_local_whisper") as fw, \
         patch.object(ai_client, "_legacy_transcribe") as legacy:
        yield {"deepgram": dg, "whisper": fw, "legacy": legacy}


def test_empty_audio_returns_empty_without_touching_any_tier(patched_chain):
    assert ai_client.transcribe_audio(b"") == ""
    patched_chain["deepgram"].assert_not_called()
    patched_chain["whisper"].assert_not_called()
    patched_chain["legacy"].assert_not_called()


def test_deepgram_success_short_circuits_chain(patched_chain):
    patched_chain["deepgram"].return_value = "from deepgram"

    out = ai_client.transcribe_audio(b"RIFF...wav")

    assert out == "from deepgram"
    patched_chain["whisper"].assert_not_called()
    patched_chain["legacy"].assert_not_called()


def test_deepgram_forwards_with_speakers_flag(patched_chain):
    patched_chain["deepgram"].return_value = "[Speaker 0]: hi"

    ai_client.transcribe_audio(b"RIFF", with_speakers=True)

    call = patched_chain["deepgram"].call_args
    assert call.kwargs["with_speakers"] is True


def test_deepgram_unavailable_falls_through_to_whisper(patched_chain):
    patched_chain["deepgram"].side_effect = DeepgramUnavailable("no key")
    patched_chain["whisper"].return_value = "from whisper"

    out = ai_client.transcribe_audio(b"RIFF")

    assert out == "from whisper"
    patched_chain["whisper"].assert_called_once_with(b"RIFF")
    patched_chain["legacy"].assert_not_called()


def test_whisper_unavailable_falls_through_to_legacy(patched_chain):
    patched_chain["deepgram"].side_effect = DeepgramUnavailable("no key")
    patched_chain["whisper"].side_effect = WhisperUnavailable("not installed")
    patched_chain["legacy"].return_value = "from openai whisper"

    out = ai_client.transcribe_audio(b"RIFF", with_speakers=True)

    assert out == "from openai whisper"
    legacy_call = patched_chain["legacy"].call_args
    assert legacy_call.args[0] == b"RIFF"
    assert legacy_call.kwargs["with_speakers"] is True


def test_legacy_failure_propagates(patched_chain):
    """The chain catches typed unavailability; raw legacy errors must reach
    the caller so the higher-level pipeline can save the audio for review."""
    patched_chain["deepgram"].side_effect = DeepgramUnavailable("no key")
    patched_chain["whisper"].side_effect = WhisperUnavailable("not installed")
    patched_chain["legacy"].side_effect = RuntimeError("openai 5xx")

    with pytest.raises(RuntimeError, match="openai 5xx"):
        ai_client.transcribe_audio(b"RIFF")


def test_unexpected_exception_in_deepgram_does_not_swallow():
    """If transcribe_with_deepgram raises something OTHER than the typed
    DeepgramUnavailable, that's a real bug — the chain must not eat it."""
    with patch.object(ai_client, "transcribe_with_deepgram", side_effect=ValueError("bug")):
        with pytest.raises(ValueError, match="bug"):
            ai_client.transcribe_audio(b"RIFF")


def test_sacred_content_section_present_in_rewrite_prompt():
    """Guard the SACRED CONTENT rules so a future refactor can't silently
    drop them. We check the section header and at least one rule per category."""
    p = ai_client._REWRITE_SYSTEM_PROMPT
    assert "SACRED CONTENT" in p
    assert "QUOTED STRINGS" in p
    assert "CODE-LIKE IDENTIFIERS" in p
    assert "PROPER NOUNS" in p
    assert "NUMBERS + UNITS" in p
    assert "URLs" in p
    # Spec rule: code identifiers must include the dotted-path form.
    assert "dotted.path" in p
