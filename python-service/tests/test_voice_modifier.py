"""Tests for the spoken "quote:" / "verbatim:" voice modifier.

Two layers:
1. Pure unit tests for ai_client.parse_voice_modifier().
2. Integration tests that drive the /transcribe-push-to-talk route handler
   directly (asyncio.run, no TestClient — avoids the app's DB-init startup),
   proving the modifier is actually wired into the live flow.
"""
from __future__ import annotations

import asyncio
import io
from unittest.mock import patch

import pytest
from starlette.datastructures import UploadFile

import ai_client
import routes


# ─── Layer 1: pure parser ────────────────────────────────────────────────────


@pytest.mark.parametrize("text", [
    "quote: the exact words",
    "verbatim: the exact words",
    "Quote: the exact words",
    "VERBATIM: the exact words",
    "quote, the exact words",      # Deepgram renders the spoken pause as a comma
    "Verbatim. the exact words",   # …or a period
    "   quote:   the exact words", # leading + trailing whitespace
])
def test_prefix_forces_verbatim_and_strips(text):
    mode, stripped = ai_client.parse_voice_modifier(text)
    assert mode == "verbatim"
    assert stripped == "the exact words"


@pytest.mark.parametrize("text", [
    "regular dictation with no prefix",
    "quoting the imam is important",   # "quoting" must NOT trigger (word boundary)
    "verbatim transcripts are useful", # no punctuation after keyword → not a command
    "the quote: was famous",           # prefix not at the start
    "",
])
def test_non_prefix_stays_rewrite(text):
    mode, stripped = ai_client.parse_voice_modifier(text)
    assert mode is None
    assert stripped == text


def test_prefix_only_yields_empty_text():
    mode, stripped = ai_client.parse_voice_modifier("verbatim:")
    assert mode == "verbatim"
    assert stripped == ""


def test_none_input_is_safe():
    assert ai_client.parse_voice_modifier(None) == (None, None)


# ─── Layer 2: route wiring ───────────────────────────────────────────────────


def _call_route(raw_transcript, *, mode="rewrite"):
    """Drive the async route handler with a mocked transcription and mocked
    polish functions. Returns (response_dict, verbatim_mock, rewrite_mock)."""
    upload = UploadFile(io.BytesIO(b"RIFF....wavbytes"), filename="d.wav")

    with patch.object(ai_client, "transcribe_audio", return_value=raw_transcript), \
         patch.object(ai_client, "polish_verbatim_aggressive",
                      return_value="VERBATIM OUT") as verbatim_mock, \
         patch.object(ai_client, "rewrite_dictation",
                      return_value="REWRITE OUT") as rewrite_mock:
        resp = asyncio.run(
            routes.transcribe_push_to_talk(
                file=upload, mode=mode, note_id=None, append=False,
            )
        )
    return resp, verbatim_mock, rewrite_mock


def test_voice_prefix_overrides_rewrite_hotkey():
    """Hotkey said rewrite, but the spoken 'quote:' must win → verbatim."""
    resp, verbatim_mock, rewrite_mock = _call_route("quote: keep these words")

    assert resp["mode"] == "verbatim"
    assert resp["text"] == "VERBATIM OUT"
    verbatim_mock.assert_called_once()
    rewrite_mock.assert_not_called()
    # The command word is stripped before polishing.
    assert verbatim_mock.call_args.args[0] == "keep these words"
    # …and the returned raw transcript no longer carries the prefix.
    assert resp["raw"] == "keep these words"


def test_no_prefix_keeps_rewrite_default():
    resp, verbatim_mock, rewrite_mock = _call_route("just a normal thought")

    assert resp["mode"] == "rewrite"
    assert resp["text"] == "REWRITE OUT"
    rewrite_mock.assert_called_once()
    verbatim_mock.assert_not_called()


def test_verbatim_hotkey_without_prefix_stays_verbatim():
    """Shift+Ctrl+Space (mode=verbatim) with no voice prefix still verbatim."""
    resp, verbatim_mock, rewrite_mock = _call_route(
        "just dictate this", mode="verbatim",
    )

    assert resp["mode"] == "verbatim"
    verbatim_mock.assert_called_once()
    rewrite_mock.assert_not_called()
