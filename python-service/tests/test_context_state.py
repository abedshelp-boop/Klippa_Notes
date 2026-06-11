"""Tests for context_state singletons (foreground/open-note + last-capture)."""
from datetime import datetime, timezone, timedelta

import context_state


def setup_function():
    """Reset module state before each test so they don't leak into each other."""
    context_state.clear_context()
    context_state.clear_last_capture()


def test_context_starts_blank():
    ctx = context_state.get_context()
    assert ctx == {"foreground": False, "open_note_id": None}


def test_set_context_round_trip():
    context_state.set_context(foreground=True, open_note_id="abc-123")
    assert context_state.get_context() == {
        "foreground": True,
        "open_note_id": "abc-123",
    }


def test_clear_context_resets():
    context_state.set_context(foreground=True, open_note_id="abc-123")
    context_state.clear_context()
    assert context_state.get_context() == {"foreground": False, "open_note_id": None}


def test_set_context_coerces_truthiness():
    """Electron sends booleans but we don't want to trust the wire format."""
    context_state.set_context(foreground=1, open_note_id="abc")  # type: ignore[arg-type]
    assert context_state.get_context()["foreground"] is True


def test_set_context_empty_open_note_id_becomes_none():
    context_state.set_context(foreground=True, open_note_id="")
    assert context_state.get_context()["open_note_id"] is None


def test_last_capture_starts_none():
    assert context_state.get_last_capture() is None


def test_set_last_capture_round_trip():
    context_state.set_last_capture("note-id-1")
    snap = context_state.get_last_capture()
    assert snap["note_id"] == "note-id-1"
    assert isinstance(snap["timestamp"], datetime)


def test_last_capture_within_window_returns_snapshot():
    context_state.set_last_capture("note-id-1")
    snap = context_state.get_last_capture(window_seconds=60)
    assert snap is not None
    assert snap["note_id"] == "note-id-1"


def test_last_capture_outside_window_returns_none():
    """Pretend the last capture happened 31 minutes ago — the 30-min window
    should expire it and return None."""
    context_state.set_last_capture("note-id-1")
    stale = datetime.now(timezone.utc) - timedelta(minutes=31)
    # Patch the stored timestamp directly to simulate clock advance without
    # needing a fake-clock harness across the whole module.
    context_state._last_capture["timestamp"] = stale
    assert context_state.get_last_capture(window_seconds=30 * 60) is None
