"""Tests for tts_client.say — graceful no-op TTS hear-back."""
from unittest.mock import MagicMock, patch

import tts_client


def setup_function():
    """Reset the warn-once flag between tests."""
    tts_client._warned = False


def test_say_no_op_on_404():
    fake_response = MagicMock()
    fake_response.status = 404
    with patch("tts_client._http_get", return_value=fake_response):
        tts_client.say("Saved to Quick Inbox")  # no raise


def test_say_no_op_on_connection_error():
    with patch("tts_client._http_get", side_effect=ConnectionError("nope")):
        tts_client.say("Saved to Quick Inbox")  # no raise


def test_say_no_op_on_timeout():
    with patch("tts_client._http_get", side_effect=TimeoutError("slow")):
        tts_client.say("Saved to Quick Inbox")  # no raise


def test_say_no_op_on_os_error():
    with patch("tts_client._http_get", side_effect=OSError("refused")):
        tts_client.say("Saved to Quick Inbox")  # no raise


def test_say_uses_short_timeout():
    """Regression guard: even on a 'success' that hangs, we time out fast."""
    captured = {}
    def fake_get(url, timeout):
        captured["timeout"] = timeout
        m = MagicMock()
        m.status = 200
        return m
    with patch("tts_client._http_get", side_effect=fake_get):
        tts_client.say("x")
    assert captured["timeout"] <= 2.0


def test_say_url_encodes_text():
    captured = {}
    def fake_get(url, timeout):
        captured["url"] = url
        m = MagicMock()
        m.status = 200
        return m
    with patch("tts_client._http_get", side_effect=fake_get):
        tts_client.say("Saved to Sapiens & Cooking")
    assert "Sapiens" in captured["url"]
    # & must be URL-encoded since it's a query separator.
    after_qs = captured["url"].split("?text=")[1]
    assert "&" not in after_qs or "%26" in captured["url"]


def test_say_empty_string_is_noop():
    """Empty input shouldn't even attempt a call."""
    with patch("tts_client._http_get") as mock_get:
        tts_client.say("")
        mock_get.assert_not_called()
