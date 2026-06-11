"""Unit tests for deepgram_client — no network calls, all SDK interactions mocked."""
from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest

import config
import deepgram_client


@pytest.fixture(autouse=True)
def _reset_module_state(monkeypatch):
    """Each test starts with a fresh client + a known key, and a fake
    `deepgram` SDK module on sys.modules so `_get_client()` doesn't try to
    actually import the real SDK."""
    monkeypatch.setattr(deepgram_client, "_client", None)
    monkeypatch.setattr(deepgram_client, "_configured_key", None)
    monkeypatch.setattr(config, "DEEPGRAM_API_KEY", "fake-key-xxx")

    fake_sdk = types.ModuleType("deepgram")
    fake_sdk.DeepgramClient = MagicMock(name="DeepgramClient")
    monkeypatch.setitem(sys.modules, "deepgram", fake_sdk)

    fake_errors = types.ModuleType("deepgram.core.api_error")

    class _ApiError(Exception):
        def __init__(self, status_code=500, body=None):
            super().__init__("api error")
            self.status_code = status_code
            self.body = body or {}

    fake_errors.ApiError = _ApiError
    monkeypatch.setitem(sys.modules, "deepgram.core.api_error", fake_errors)

    yield {"sdk": fake_sdk, "errors": fake_errors}


def _wire_response(fake_sdk, *, transcript="hello world", words=None):
    """Build the chain of mocks that deepgram_client expects to traverse."""
    alt = MagicMock()
    alt.transcript = transcript
    alt.words = words or []

    channel = MagicMock()
    channel.alternatives = [alt]

    response = MagicMock()
    response.results.channels = [channel]

    client_instance = MagicMock()
    client_instance.listen.v1.media.transcribe_file.return_value = response
    fake_sdk.DeepgramClient.return_value = client_instance
    return client_instance, response


def test_empty_bytes_short_circuits(_reset_module_state):
    """Empty audio must NOT hit the SDK or count as a fallback trigger."""
    fake_sdk = _reset_module_state["sdk"]
    fake_sdk.DeepgramClient.assert_not_called()

    assert deepgram_client.transcribe_with_deepgram(b"") == ""
    fake_sdk.DeepgramClient.assert_not_called()


def test_missing_key_raises_unavailable(monkeypatch, _reset_module_state):
    monkeypatch.setattr(config, "DEEPGRAM_API_KEY", "")
    with pytest.raises(deepgram_client.DeepgramUnavailable, match="not set"):
        deepgram_client.transcribe_with_deepgram(b"RIFF....")


def test_basic_call_uses_nova3_with_safe_defaults(_reset_module_state):
    client_instance, _ = _wire_response(_reset_module_state["sdk"])

    out = deepgram_client.transcribe_with_deepgram(b"RIFF...wavbytes")

    assert out == "hello world"
    call = client_instance.listen.v1.media.transcribe_file.call_args
    assert call.kwargs["request"] == b"RIFF...wavbytes"
    assert call.kwargs["model"] == "nova-3"
    assert call.kwargs["smart_format"] is True
    assert call.kwargs["punctuate"] is True
    assert "diarize" not in call.kwargs  # off by default
    assert "language" not in call.kwargs  # auto-detect by default


def test_with_speakers_forwards_diarize_and_groups_words(_reset_module_state):
    words = [
        MagicMock(speaker=0, punctuated_word="Hello,", word="hello"),
        MagicMock(speaker=0, punctuated_word="world.", word="world"),
        MagicMock(speaker=1, punctuated_word="Hi", word="hi"),
        MagicMock(speaker=1, punctuated_word="back.", word="back"),
    ]
    client_instance, _ = _wire_response(
        _reset_module_state["sdk"], transcript="ignored", words=words,
    )

    out = deepgram_client.transcribe_with_deepgram(b"RIFF", with_speakers=True)

    assert client_instance.listen.v1.media.transcribe_file.call_args.kwargs["diarize"] is True
    assert "[Speaker 0]: Hello, world." in out
    assert "[Speaker 1]: Hi back." in out


def test_with_speakers_falls_back_to_transcript_when_no_words(_reset_module_state):
    _wire_response(_reset_module_state["sdk"], transcript="just a flat transcript", words=[])

    out = deepgram_client.transcribe_with_deepgram(b"RIFF", with_speakers=True)

    assert out == "just a flat transcript"


def test_language_hint_is_forwarded(_reset_module_state):
    client_instance, _ = _wire_response(_reset_module_state["sdk"])

    deepgram_client.transcribe_with_deepgram(b"RIFF", language_hint="ar")

    assert client_instance.listen.v1.media.transcribe_file.call_args.kwargs["language"] == "ar"


def test_api_error_becomes_unavailable(_reset_module_state):
    ApiError = _reset_module_state["errors"].ApiError
    client_instance = MagicMock()
    client_instance.listen.v1.media.transcribe_file.side_effect = ApiError(status_code=429)
    _reset_module_state["sdk"].DeepgramClient.return_value = client_instance

    with pytest.raises(deepgram_client.DeepgramUnavailable, match="429"):
        deepgram_client.transcribe_with_deepgram(b"RIFF")


def test_generic_exception_becomes_unavailable(_reset_module_state):
    client_instance = MagicMock()
    client_instance.listen.v1.media.transcribe_file.side_effect = RuntimeError("boom")
    _reset_module_state["sdk"].DeepgramClient.return_value = client_instance

    with pytest.raises(deepgram_client.DeepgramUnavailable, match="boom"):
        deepgram_client.transcribe_with_deepgram(b"RIFF")


def test_unexpected_response_shape_becomes_unavailable(_reset_module_state):
    broken = MagicMock()
    broken.results.channels = []  # IndexError when we ask for [0]
    client_instance = MagicMock()
    client_instance.listen.v1.media.transcribe_file.return_value = broken
    _reset_module_state["sdk"].DeepgramClient.return_value = client_instance

    with pytest.raises(deepgram_client.DeepgramUnavailable, match="response shape"):
        deepgram_client.transcribe_with_deepgram(b"RIFF")


def test_client_is_recreated_when_key_rotates(_reset_module_state):
    _wire_response(_reset_module_state["sdk"])
    deepgram_client.transcribe_with_deepgram(b"RIFF")
    first_count = _reset_module_state["sdk"].DeepgramClient.call_count

    # Rotate the key; expect a new client instance the next call.
    import config as cfg
    cfg.DEEPGRAM_API_KEY = "rotated-key"  # noqa: S105 — test sentinel
    _wire_response(_reset_module_state["sdk"])
    deepgram_client.transcribe_with_deepgram(b"RIFF")
    assert _reset_module_state["sdk"].DeepgramClient.call_count == first_count + 1
