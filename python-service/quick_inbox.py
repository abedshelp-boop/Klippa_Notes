"""
Quick Inbox singleton — the always-there parking-lot note.

The Quick Inbox is a special note created on first launch and protected from
deletion. Voice captures with no clear destination land here so the user can
sort them later (at the desk, with their hands free).

Lifecycle:
  - ensure_quick_inbox(): create if missing, return existing otherwise.
    Called from FastAPI startup (routes.py) so every launch has it.
  - is_quick_inbox_id(id): cheap check used by the picker and sidebar to
    suppress delete affordances and special-case the row at top.

Identification: the database column `notes.is_quick_inbox` (added in the
schema migration) is the source of truth. We DO NOT identify by title —
users may rename and we want the singleton to survive that.
"""
from __future__ import annotations

import asyncio
from typing import Optional

import database as db

_ensure_lock = asyncio.Lock()
_cached_id: Optional[str] = None


async def ensure_quick_inbox() -> dict:
    """Idempotent: returns the existing Quick Inbox or creates one.

    Uses an asyncio.Lock to prevent the create-twice race when two startup
    callers fire concurrently. The first wins; the second sees the row on
    its retry.
    """
    global _cached_id
    async with _ensure_lock:
        existing = await db.get_quick_inbox()
        if existing:
            _cached_id = existing["id"]
            return existing
        created = await db.create_quick_inbox()
        _cached_id = created["id"]
        return created


async def is_quick_inbox_id(note_id: Optional[str]) -> bool:
    """Fast check: is this note id the Quick Inbox?

    Uses the cached id when available; falls through to a DB lookup so we're
    correct even after a fresh process start (cache empty)."""
    global _cached_id
    if not note_id:
        return False
    if _cached_id is not None:
        return note_id == _cached_id
    inbox = await db.get_quick_inbox()
    if inbox is None:
        return False
    _cached_id = inbox["id"]
    return note_id == _cached_id


def get_cached_id() -> Optional[str]:
    """Synchronous read of the cached Quick Inbox id, for callers that
    already know ensure_quick_inbox() has run. Returns None on cold cache —
    callers should treat None as 'not yet ensured' and fall back gracefully."""
    return _cached_id
