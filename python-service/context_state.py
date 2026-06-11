"""
In-memory state shared between Electron and the Python service.

Two singletons:

  - CONTEXT: which Electron window is foregrounded and which note (if any) is
    currently open in it. Pushed from Electron via POST /context. Voice
    routing uses this as the no-qualifier default ("Hey Deen, [content]" with
    main window foreground + a note open → route there silently).

  - LAST_CAPTURE: which note we most recently appended/created. Updated by
    note_generator after every successful save. Voice pattern "continue" uses
    this with a configurable freshness window (default 30 min).

Both use the same threading.Lock pattern as target.py — they're touched from
the async FastAPI loop AND the synchronous wake-word thread, so a lock is
needed even though most calls are cheap.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Optional

_lock = threading.Lock()

_context = {"foreground": False, "open_note_id": None}
_last_capture: dict = {"note_id": None, "timestamp": None}


# ─── Context ────────────────────────────────────────────────────────────────

def get_context() -> dict:
    """Snapshot of {foreground: bool, open_note_id: str | None}."""
    with _lock:
        return dict(_context)


def set_context(foreground, open_note_id) -> None:
    """Replace the context. Called from POST /context.

    Wire format is JSON, so we coerce: foreground -> bool, falsy open_note_id
    (None, empty string) -> None.
    """
    with _lock:
        _context["foreground"] = bool(foreground)
        _context["open_note_id"] = open_note_id or None


def clear_context() -> None:
    """Wipe to defaults. Used by tests and on Electron disconnect (no
    /context call within ~5s → blank out)."""
    with _lock:
        _context["foreground"] = False
        _context["open_note_id"] = None


# ─── Last capture ───────────────────────────────────────────────────────────

def get_last_capture(window_seconds: int = 30 * 60) -> Optional[dict]:
    """Return {note_id, timestamp} if the last capture is within `window_seconds`.
    Returns None if no capture has happened or it's older than the window.

    The 30-minute default matches the voice spec's "continue" rule.
    """
    with _lock:
        nid = _last_capture["note_id"]
        ts = _last_capture["timestamp"]
        if nid is None or ts is None:
            return None
        age = (datetime.now(timezone.utc) - ts).total_seconds()
        if age > window_seconds:
            return None
        return {"note_id": nid, "timestamp": ts}


def set_last_capture(note_id: str) -> None:
    """Stamp the last capture. Called by note_generator after each save."""
    with _lock:
        _last_capture["note_id"] = note_id
        _last_capture["timestamp"] = datetime.now(timezone.utc)


def clear_last_capture() -> None:
    """Reset to None. Used by tests."""
    with _lock:
        _last_capture["note_id"] = None
        _last_capture["timestamp"] = None
