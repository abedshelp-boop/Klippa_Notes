"""Tests for haiku_client — Haiku 4.5 fallback with graceful skip."""
from unittest.mock import MagicMock, patch

import pytest

import haiku_client


def setup_function():
    """Reset module cache between tests."""
    haiku_client._client_cache["key"] = None
    haiku_client._client_cache["client"] = None


@patch("haiku_client._get_api_key", return_value="fake-key")
@patch("haiku_client._get_client")
def test_pick_best_returns_chosen_id(mock_get_client, _key):
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text='{"note_id":"n1","confidence":"high"}')]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_msg
    mock_get_client.return_value = fake_client

    result = haiku_client.pick_best(
        query="Sapiens",
        candidates=[
            {"id": "n1", "title": "Sapiens"},
            {"id": "n2", "title": "Sapiens chapter 2"},
        ],
        content="the author argues humans love stories.",
    )
    assert result == {"note_id": "n1", "confidence": "high"}


@patch("haiku_client._get_api_key", return_value="fake-key")
@patch("haiku_client._get_client")
def test_pick_best_returns_none_on_invalid_json(mock_get_client, _key):
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text="this is not json")]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_msg
    mock_get_client.return_value = fake_client

    result = haiku_client.pick_best(
        query="x", candidates=[{"id": "n1", "title": "Sapiens"}], content="hi"
    )
    assert result is None


@patch("haiku_client._get_api_key", return_value="fake-key")
@patch("haiku_client._get_client", side_effect=RuntimeError("network down"))
def test_pick_best_returns_none_on_exception(mock_get_client, _key):
    result = haiku_client.pick_best(
        query="x", candidates=[{"id": "n1", "title": "Sapiens"}], content="hi"
    )
    assert result is None


@patch("haiku_client._get_api_key", return_value="fake-key")
@patch("haiku_client._get_client")
def test_pick_best_returns_none_when_no_candidates(mock_get_client, _key):
    result = haiku_client.pick_best(query="x", candidates=[], content="hi")
    assert result is None
    mock_get_client.assert_not_called()


def test_pick_best_skips_when_no_key(monkeypatch):
    """If ANTHROPIC_API_KEY is absent, pick_best must not even attempt a call."""
    monkeypatch.setattr(haiku_client, "_get_api_key", lambda: None)
    result = haiku_client.pick_best(
        query="x", candidates=[{"id": "n1", "title": "Sapiens"}], content="hi"
    )
    assert result is None


@patch("haiku_client._get_api_key", return_value="fake-key")
@patch("haiku_client._get_client")
def test_pick_best_rejects_hallucinated_id(mock_get_client, _key):
    """If Haiku returns an id not in candidates, we MUST refuse."""
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text='{"note_id":"hallucinated","confidence":"high"}')]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_msg
    mock_get_client.return_value = fake_client

    result = haiku_client.pick_best(
        query="x", candidates=[{"id": "n1", "title": "Sapiens"}], content="hi"
    )
    assert result is None


@patch("haiku_client._get_api_key", return_value="fake-key")
@patch("haiku_client._get_client")
def test_pick_best_accepts_null_note_id(mock_get_client, _key):
    """Haiku saying 'I don't know' is a valid answer."""
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text='{"note_id":null,"confidence":"low"}')]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_msg
    mock_get_client.return_value = fake_client

    result = haiku_client.pick_best(
        query="x", candidates=[{"id": "n1", "title": "Sapiens"}], content="hi"
    )
    assert result == {"note_id": None, "confidence": "low"}
