"""Unit tests for faster_whisper_fallback — no actual model load."""
from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest

import faster_whisper_fallback as fw


@pytest.fixture(autouse=True)
def _reset_module_state(monkeypatch):
    """Reset the cached singleton and stub the `faster_whisper` SDK so we
    never try to download a real model during tests."""
    monkeypatch.setattr(fw, "_model", None)

    fake_sdk = types.ModuleType("faster_whisper")
    fake_sdk.WhisperModel = MagicMock(name="WhisperModel")
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_sdk)
    yield {"sdk": fake_sdk}


def _wire_model(fake_sdk, segments=None, language="en", language_prob=0.99):
    """Build the model + segment/info chain faster-whisper returns."""
    model_instance = MagicMock(name="WhisperModelInstance")
    seg_objs = [
        MagicMock(text=text, start=i, end=i + 1)
        for i, text in enumerate(segments or [" hello ", " world "])
    ]
    info = MagicMock(language=language, language_probability=language_prob)
    model_instance.transcribe.return_value = (iter(seg_objs), info)
    fake_sdk.WhisperModel.return_value = model_instance
    return model_instance


def test_empty_bytes_short_circuits(_reset_module_state):
    fake_sdk = _reset_module_state["sdk"]
    assert fw.transcribe_with_local_whisper(b"") == ""
    fake_sdk.WhisperModel.assert_not_called()


def test_basic_transcribe_concatenates_segments(_reset_module_state):
    model_instance = _wire_model(_reset_module_state["sdk"])

    out = fw.transcribe_with_local_whisper(b"RIFF...wav")

    assert out == "hello world"
    model_instance.transcribe.assert_called_once()
    kwargs = model_instance.transcribe.call_args.kwargs
    assert kwargs["beam_size"] == 5
    assert kwargs["vad_filter"] is False  # upstream VAD already trimmed silence
    assert kwargs["language"] is None  # auto-detect by default


def test_language_hint_is_forwarded(_reset_module_state):
    model_instance = _wire_model(_reset_module_state["sdk"])

    fw.transcribe_with_local_whisper(b"RIFF", language_hint="ar")

    assert model_instance.transcribe.call_args.kwargs["language"] == "ar"


def test_default_model_size_is_small(monkeypatch, _reset_module_state):
    monkeypatch.delenv("FASTER_WHISPER_MODEL_SIZE", raising=False)
    _wire_model(_reset_module_state["sdk"])

    fw.transcribe_with_local_whisper(b"RIFF")

    args, kwargs = _reset_module_state["sdk"].WhisperModel.call_args
    assert args[0] == "small"
    assert kwargs["device"] == "cpu"
    assert kwargs["compute_type"] == "int8"


def test_model_size_env_override(monkeypatch, _reset_module_state):
    monkeypatch.setenv("FASTER_WHISPER_MODEL_SIZE", "base")
    _wire_model(_reset_module_state["sdk"])

    fw.transcribe_with_local_whisper(b"RIFF")

    assert _reset_module_state["sdk"].WhisperModel.call_args.args[0] == "base"


def test_model_load_failure_becomes_unavailable(_reset_module_state):
    _reset_module_state["sdk"].WhisperModel.side_effect = RuntimeError("disk full")

    with pytest.raises(fw.WhisperUnavailable, match="disk full"):
        fw.transcribe_with_local_whisper(b"RIFF")


def test_transcribe_failure_becomes_unavailable(_reset_module_state):
    model_instance = MagicMock()
    model_instance.transcribe.side_effect = OSError("bad audio")
    _reset_module_state["sdk"].WhisperModel.return_value = model_instance

    with pytest.raises(fw.WhisperUnavailable, match="bad audio"):
        fw.transcribe_with_local_whisper(b"RIFF")


def test_missing_sdk_becomes_unavailable(monkeypatch, _reset_module_state):
    # Drop the stub — the import inside _get_model() will then fail with
    # ModuleNotFoundError because the real package isn't installed in tests.
    monkeypatch.delitem(sys.modules, "faster_whisper", raising=False)
    # Force the real import path to fail by registering a finder that returns None
    # for `faster_whisper`. Simpler: just rely on the actual SDK being absent.
    # If a previous test populated the cache, we already cleared _model in the
    # autouse fixture; that's enough.

    # If faster-whisper happens to actually be installed in this venv we can't
    # assert ImportError — skip cleanly in that case.
    try:
        import faster_whisper  # noqa: F401 — probe only
        pytest.skip("faster-whisper is installed in this venv; can't assert ImportError")
    except ImportError:
        pass

    with pytest.raises(fw.WhisperUnavailable, match="not installed"):
        fw.transcribe_with_local_whisper(b"RIFF")


def test_model_is_cached_across_calls(_reset_module_state):
    _wire_model(_reset_module_state["sdk"])

    fw.transcribe_with_local_whisper(b"RIFF")
    fw.transcribe_with_local_whisper(b"RIFF")

    # WhisperModel constructor must have run exactly once across both calls.
    assert _reset_module_state["sdk"].WhisperModel.call_count == 1
