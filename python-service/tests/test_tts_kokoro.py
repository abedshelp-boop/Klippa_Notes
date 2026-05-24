"""Unit tests for tts_kokoro — mocks the SDK so no model is loaded."""
from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

import config
import tts_kokoro


@pytest.fixture(autouse=True)
def _reset_module_state(monkeypatch, tmp_path: Path):
    """Reset the cached singleton, stub the kokoro_onnx SDK, and point the
    config paths at temp files that actually exist so the existence check
    passes."""
    monkeypatch.setattr(tts_kokoro, "_kokoro", None)
    monkeypatch.setattr(tts_kokoro, "_configured_paths", None)

    model_file = tmp_path / "kokoro-v1.0.onnx"
    voices_file = tmp_path / "voices-v1.0.bin"
    model_file.write_bytes(b"fake-onnx")
    voices_file.write_bytes(b"fake-voices")
    monkeypatch.setattr(config, "KOKORO_MODEL_PATH", str(model_file))
    monkeypatch.setattr(config, "KOKORO_VOICES_PATH", str(voices_file))
    monkeypatch.setattr(config, "KOKORO_VOICE", "af_heart")

    fake_sdk = types.ModuleType("kokoro_onnx")
    fake_sdk.Kokoro = MagicMock(name="Kokoro")
    monkeypatch.setitem(sys.modules, "kokoro_onnx", fake_sdk)

    yield {"sdk": fake_sdk, "model_file": model_file, "voices_file": voices_file}


def _wire_synth(fake_sdk, samples=None, sample_rate=24000):
    kokoro_instance = MagicMock(name="KokoroInstance")
    if samples is None:
        # One second of a 440Hz-ish sine — content doesn't matter, just needs
        # to encode to a valid WAV.
        samples = (np.sin(np.linspace(0, 2 * np.pi, sample_rate)) * 0.3).astype(np.float32)
    kokoro_instance.create.return_value = (samples, sample_rate)
    fake_sdk.Kokoro.return_value = kokoro_instance
    return kokoro_instance


def test_empty_text_returns_empty_bytes(_reset_module_state):
    fake_sdk = _reset_module_state["sdk"]
    assert tts_kokoro.synthesize_to_wav("") == b""
    assert tts_kokoro.synthesize_to_wav("   \n  ") == b""
    fake_sdk.Kokoro.assert_not_called()


def test_basic_synth_returns_riff_wav_bytes(_reset_module_state):
    kokoro_instance = _wire_synth(_reset_module_state["sdk"])

    wav = tts_kokoro.synthesize_to_wav("Saved to Sapiens")

    # Smoke-test the WAV header — the renderer only cares that this is
    # something HTMLAudioElement will play. RIFF / WAVE marks suffice.
    assert wav.startswith(b"RIFF")
    assert wav[8:12] == b"WAVE"
    kokoro_instance.create.assert_called_once()
    call = kokoro_instance.create.call_args
    assert call.args[0] == "Saved to Sapiens"
    assert call.kwargs["voice"] == "af_heart"
    assert call.kwargs["lang"] == "en-us"
    assert call.kwargs["speed"] == 1.05


def test_voice_argument_overrides_config(_reset_module_state):
    kokoro_instance = _wire_synth(_reset_module_state["sdk"])

    tts_kokoro.synthesize_to_wav("Hello", voice="bf_emma")

    assert kokoro_instance.create.call_args.kwargs["voice"] == "bf_emma"


def test_missing_model_file_raises_unavailable(monkeypatch, _reset_module_state):
    monkeypatch.setattr(config, "KOKORO_MODEL_PATH", "/no/such/model.onnx")
    with pytest.raises(tts_kokoro.TTSUnavailable, match="not found"):
        tts_kokoro.synthesize_to_wav("hi")


def test_missing_voices_file_raises_unavailable(monkeypatch, _reset_module_state):
    monkeypatch.setattr(config, "KOKORO_VOICES_PATH", "/no/such/voices.bin")
    with pytest.raises(tts_kokoro.TTSUnavailable, match="not found"):
        tts_kokoro.synthesize_to_wav("hi")


def test_synth_failure_becomes_unavailable(_reset_module_state):
    kokoro_instance = MagicMock()
    kokoro_instance.create.side_effect = RuntimeError("voice not found")
    _reset_module_state["sdk"].Kokoro.return_value = kokoro_instance

    with pytest.raises(tts_kokoro.TTSUnavailable, match="voice not found"):
        tts_kokoro.synthesize_to_wav("hi")


def test_silent_output_returns_empty_bytes(_reset_module_state):
    _wire_synth(_reset_module_state["sdk"], samples=np.zeros(0, dtype=np.float32))
    assert tts_kokoro.synthesize_to_wav("hi") == b""


def test_model_is_cached_across_calls(_reset_module_state):
    _wire_synth(_reset_module_state["sdk"])

    tts_kokoro.synthesize_to_wav("one")
    tts_kokoro.synthesize_to_wav("two")
    tts_kokoro.synthesize_to_wav("three")

    assert _reset_module_state["sdk"].Kokoro.call_count == 1


def test_paths_change_recreates_kokoro(_reset_module_state, monkeypatch, tmp_path: Path):
    _wire_synth(_reset_module_state["sdk"])
    tts_kokoro.synthesize_to_wav("first")

    # Swap to a different model file — Kokoro should be re-instantiated.
    new_model = tmp_path / "kokoro-v2.onnx"
    new_model.write_bytes(b"different")
    monkeypatch.setattr(config, "KOKORO_MODEL_PATH", str(new_model))

    _wire_synth(_reset_module_state["sdk"])
    tts_kokoro.synthesize_to_wav("second")

    assert _reset_module_state["sdk"].Kokoro.call_count == 2
