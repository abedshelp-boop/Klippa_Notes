"""
In-memory store for the currently playing video context,
reported by the Klippa Chrome extension.
"""

import threading
from datetime import datetime, timezone

_lock = threading.Lock()
_current = None  # { "title": str, "url": str, "updated_at": str } or None


def set_video(title: str, url: str):
    global _current
    with _lock:
        _current = {
            "title": title,
            "url": url,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }


def get_video() -> dict | None:
    with _lock:
        return dict(_current) if _current else None


def clear_video():
    global _current
    with _lock:
        _current = None
