"""
Output-language preference state, in-memory.

Mirrors target.py's shape so routes.py can use both modules the same way.
Electron is the source of truth (persists to app-state.json) and re-asserts
the current value to Python on every app launch.

Codes follow ISO 639-1 where possible. "auto" is the sentinel for the user's
"Global" choice — preserves whatever language the LLM would have picked
based on the system audio (today's behavior).
"""

from threading import Lock

_DEFAULT = {
    "code": "auto",
    "label": "Global",
    "emoji": "\U0001F30D",  # 🌍
}

_state = dict(_DEFAULT)
_lock = Lock()


def get_language() -> dict:
    """Return a copy of the current language preference."""
    with _lock:
        return dict(_state)


def set_language(code: str, label: str, emoji: str) -> dict:
    """Replace the current language. Returns the new state."""
    with _lock:
        _state["code"] = code
        _state["label"] = label
        _state["emoji"] = emoji
        return dict(_state)


def clear_language() -> dict:
    """Reset to default (Global / auto)."""
    with _lock:
        _state.update(_DEFAULT)
        return dict(_state)
