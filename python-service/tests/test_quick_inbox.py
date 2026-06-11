"""Tests for Quick Inbox: DB column, helpers, delete-guard, ensure singleton."""
import importlib
import sys
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_db(monkeypatch):
    """Point DB_PATH at a temp file BEFORE config/database are imported so
    init_db creates a fresh schema we can poke at."""
    tmp = Path(tempfile.mkdtemp()) / "test.db"
    monkeypatch.setenv("DEEN_NOTES_DB_OVERRIDE", str(tmp))

    # Force a fresh import of config + database so the env var takes effect.
    for mod_name in ("config", "database", "quick_inbox"):
        if mod_name in sys.modules:
            del sys.modules[mod_name]
    import config  # noqa: F401
    import database
    importlib.reload(database)

    yield database

    # Cleanup
    if tmp.exists():
        tmp.unlink()
    for mod_name in ("config", "database", "quick_inbox"):
        if mod_name in sys.modules:
            del sys.modules[mod_name]


@pytest.mark.asyncio
async def test_is_quick_inbox_column_exists_after_init(tmp_db):
    await tmp_db.init_db()
    import aiosqlite
    async with aiosqlite.connect(tmp_db.DB_PATH) as db:
        cursor = await db.execute("PRAGMA table_info(notes)")
        cols = {row[1] for row in await cursor.fetchall()}
    assert "is_quick_inbox" in cols


@pytest.mark.asyncio
async def test_get_quick_inbox_returns_none_when_absent(tmp_db):
    await tmp_db.init_db()
    result = await tmp_db.get_quick_inbox()
    assert result is None


@pytest.mark.asyncio
async def test_create_quick_inbox_then_get_returns_it(tmp_db):
    await tmp_db.init_db()
    inbox = await tmp_db.create_quick_inbox()
    assert inbox["is_quick_inbox"] == 1
    assert inbox["title"] == "Quick Inbox"
    fetched = await tmp_db.get_quick_inbox()
    assert fetched["id"] == inbox["id"]


@pytest.mark.asyncio
async def test_delete_note_refuses_quick_inbox(tmp_db):
    await tmp_db.init_db()
    inbox = await tmp_db.create_quick_inbox()
    deleted = await tmp_db.delete_note(inbox["id"])
    assert deleted is False
    still_there = await tmp_db.get_quick_inbox()
    assert still_there is not None


@pytest.mark.asyncio
async def test_delete_note_still_works_on_regular_notes(tmp_db):
    """Regression guard: protecting Quick Inbox must not break normal deletes."""
    await tmp_db.init_db()
    note = await tmp_db.create_note(title="A", content="b", tags=[])
    deleted = await tmp_db.delete_note(note["id"])
    assert deleted is True


# ─── quick_inbox module tests ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ensure_quick_inbox_creates_when_missing(tmp_db):
    await tmp_db.init_db()
    import quick_inbox
    inbox = await quick_inbox.ensure_quick_inbox()
    assert inbox["title"] == "Quick Inbox"
    assert inbox["is_quick_inbox"] == 1


@pytest.mark.asyncio
async def test_ensure_quick_inbox_idempotent(tmp_db):
    await tmp_db.init_db()
    import quick_inbox
    # Reset the module-level cache so test isolation holds.
    quick_inbox._cached_id = None
    first = await quick_inbox.ensure_quick_inbox()
    second = await quick_inbox.ensure_quick_inbox()
    assert first["id"] == second["id"]


@pytest.mark.asyncio
async def test_is_quick_inbox_id_matches(tmp_db):
    await tmp_db.init_db()
    import quick_inbox
    quick_inbox._cached_id = None
    inbox = await quick_inbox.ensure_quick_inbox()
    assert await quick_inbox.is_quick_inbox_id(inbox["id"]) is True
    assert await quick_inbox.is_quick_inbox_id("not-a-real-id") is False
    assert await quick_inbox.is_quick_inbox_id(None) is False
