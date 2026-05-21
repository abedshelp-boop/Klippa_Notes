"""
In-memory store for the current note routing target.

Replaces the old `video_context` module. Instead of routing notes by matching
a video URL (which required the Chrome extension), routing is now driven
explicitly by the user via the bubble's file picker.

State shape:
  - note_id (str | None): the note all captures should append to.
  - create_new_pending (bool): user picked "Create new file"; on the next
    capture we create a new note and pin note_id to it.

If both fields are unset, capture falls back to "create one note per capture".
"""

import threading


_lock = threading.Lock()
_state = {"note_id": None, "create_new_pending": False}


def get_target() -> dict:
    """Return a snapshot of the current target. Always returns a fresh dict
    so the caller can safely keep using it after subsequent mutations."""
    with _lock:
        return dict(_state)


def set_target(note_id: str | None):
    """Pin captures to a specific note. Clears the create_new_pending flag."""
    global _state
    with _lock:
        _state = {"note_id": note_id, "create_new_pending": False}


def set_create_new_pending():
    """User picked 'Create new file'. The next capture will create a new
    note and pin note_id to it."""
    global _state
    with _lock:
        _state = {"note_id": None, "create_new_pending": True}


def clear_target():
    """Return to the default 'one note per capture' behavior."""
    global _state
    with _lock:
        _state = {"note_id": None, "create_new_pending": False}
