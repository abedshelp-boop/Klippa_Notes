---
title: Voice Routing v1 — Implementation Plan
date: 2026-05-24
status: ready-to-execute
spec: docs/superpowers/specs/2026-05-24-canvas-redesign-design.md (Voice capture section)
sub_project: 5 of N (Voice Routing v1)
worktree: .claude/worktrees/canvas-5-voice-routing
branch: canvas/5-voice-routing (off main)
parallel_safe_with: [1, 3, 4]
---

# Voice Routing v1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **For every task that's marked "tests-only" or "verification-only" below: production-code edits OUTSIDE the named deliverables require STOP + report `DONE_WITH_CONCERNS` — do not silently land production fixes alongside test changes.**

**Goal:** Implement the 4-pattern "Hey Deen" voice grammar that decides WHERE a capture lands (Quick Inbox / named note / new note / continue), with a hands-free disambiguation loop, a Quick Inbox singleton, a context-aware desktop bubble, and a pinboard-snapshot picker for desk mode.

**Architecture:** Three-layer routing in Python — grammar parser → local matcher (rapidfuzz + optional sentence-transformers embedding) → Haiku 4.5 fallback for ambiguous/low-confidence cases. Disambiguation reuses the existing `mic_listener.record_command()` plus a new `tts_client` that no-ops gracefully until Sub-project 4 ships `/tts/say`. Electron picker is rewritten as a CSS-grid "pinboard snapshot" of note mini-cards with Quick Inbox sticky at top. `electron/main.js` tracks foreground+open-note state and pushes it to Python via a new `/context` endpoint so voice routing can use it as the no-qualifier default.

**Tech stack additions:** `anthropic` (Haiku 4.5), `sentence-transformers` (`all-MiniLM-L6-v2`, 80 MB CPU model — optional; routing degrades gracefully without it), `rapidfuzz` (fuzzy string scoring), `pytest-asyncio` (already required by existing pytest setup).

**Out of scope (deferred):**
- Structure-aware in-canvas placement of cards (Sub-project 6 — this sub-project only routes to a NOTE, not into a frame).
- Canvas UI itself (Sub-projects 1 + 6).
- Dictation modifier hotkeys (Sub-project 4 — Ctrl+Space / Shift+Ctrl+Space).
- Auto-cleanup suggestions for Quick Inbox ("these look like Recipes — move?").
- Migration of existing per-group structure into outer-canvas frames.

---

## File structure

**Create (Python):**
- `python-service/quick_inbox.py` — ensure-on-startup + protection + lookup
- `python-service/voice_routing.py` — grammar parser + `route()` decision function
- `python-service/title_matcher.py` — rapidfuzz scoring + optional embedding similarity
- `python-service/haiku_client.py` — thin Anthropic Haiku 4.5 client with graceful-skip if no key
- `python-service/context_state.py` — foreground/open-note + last-capture singletons (mirrors `target.py`)
- `python-service/tts_client.py` — POST to `/tts/say` with graceful no-op
- `python-service/tests/test_quick_inbox.py`
- `python-service/tests/test_voice_routing.py`
- `python-service/tests/test_title_matcher.py`
- `python-service/tests/test_haiku_client.py`
- `python-service/tests/test_context_state.py`
- `python-service/tests/test_tts_client.py`

**Modify (Python):**
- `python-service/database.py` — add `is_quick_inbox INTEGER DEFAULT 0` column + migration; expose `get_quick_inbox()`; protect delete
- `python-service/routes.py` — `/context` GET+POST, Quick Inbox bootstrap in startup, `/notes/{id}` DELETE 409 guard for Quick Inbox
- `python-service/main.py` — call voice routing inside `on_wake_word_detected` after command transcription; wire disambiguation loop; update `context_state.last_capture` after save
- `python-service/note_generator.py` — accept a `routing_decision` arg and use it to pick destination; call `tts_client.say()` after save

**Modify (Electron):**
- `electron/main.js` — track main-window focus + open-note id; POST `/context` on change; bubble-click context-aware path; new IPC handlers for renderer-side note-open broadcasts
- `electron/bubble.html` — minor copy + class-prefix cleanup (`.bubble-*`); no new behavior
- `electron/picker.html` — full rewrite of body+script: pinboard grid with mini cards + sticky Quick Inbox
- `electron/picker-preload.js` — add `getPickerSnapshot()` (returns note grid data including Quick Inbox)
- `electron/preload.js` — add `onNoteOpenChanged(cb)` for renderer→main note-open broadcasts (no, reverse direction: renderer notifies main when active note changes; main posts to Python)

**Modify (Renderer):**
- `src/App.jsx` — on view/activeNoteId change, push the open-note id to electron via new `window.electronAPI.notifyOpenNote(id)`; in delete handler, refuse Quick Inbox
- `src/components/Sidebar.jsx` — render Quick Inbox row at top with 📥 icon; hide from "Archive" filter view; suppress delete button

---

## Test happy-path walkthrough

Before any task starts, trace the four voice patterns end-to-end against current production code to surface integration risks:

1. **`"Hey Deen, [content]"`** — wake-word fires → `on_wake_word_detected` → `record_command()` → `process_note(target=...)`. **Today** `target` carries pinned-note + create-new-pending. **After this plan**: `process_note` receives `routing_decision` instead. The command transcript has no qualifier prefix → `parse_command` returns `kind="inbox"` (unless `context_state.foreground_open_note_id` is set, in which case → `kind="existing"` on that note). Save → broadcast → `tts_client.say("Saved to Quick Inbox")`.
2. **`"Hey Deen, in Sapiens, [content]"`** — same up to transcript. `parse_command` returns `kind="in", qualifier="Sapiens"`. `title_matcher.score_all(qualifier, notes)` returns ranked candidates. Top score > 0.85 + clear gap → high confidence → route. Mid-confidence → Haiku fallback. Ambiguous → disambiguation loop.
3. **`"Hey Deen, new note about cooking eggs, [content]"`** — `parse_command` → `kind="new", qualifier="cooking eggs"`. Title cased → "Cooking eggs". `routing_decision.kind="create_new"`. `process_note` creates note, pins target to it (matches existing `create_new_pending` semantics).
4. **`"Hey Deen, continue, [content]"`** — `parse_command` → `kind="continue"`. `context_state.get_last_capture()` returns `{note_id, timestamp}` if within 30 min, else None. If None → disambiguation loop ("nothing to continue — name a note or say 'inbox'"). If present → route there.

**Branches that don't yet have a defined production code path and need ADDED logic (caught upfront, not in implementer's diff):**
- `note_generator.process_note` currently picks destination from `target_state` only. New plan: it accepts a `routing_decision` and uses that. Existing `target_state` fallback REMAINS as the no-qualifier-no-context default. (Task 14 wires this in.)
- The disambiguation listen loop is brand new — it currently doesn't exist. (Task 12.)
- TTS hear-back hits `/tts/say` which Sub-project 4 owns. Today the endpoint doesn't exist → `tts_client.say` MUST swallow 404. (Task 10.)

If any task's implementer finds a fifth boundary case not listed above, that's a **STOP and report `DONE_WITH_CONCERNS`** moment — do not invent a transition.

---

## Phase A — Foundation

### Task 1: Worktree dev setup

**Files:**
- Junction (Windows): `.claude/worktrees/canvas-5-voice-routing/node_modules` → main-repo's `node_modules`
- Junction (Windows): `.claude/worktrees/canvas-5-voice-routing/python-service/venv` → main-repo's `python-service/venv`
- Install (worktree venv via the junction): `anthropic`, `sentence-transformers`, `rapidfuzz`, `pytest-asyncio`

**Why junctions, not symlinks:** on Windows from git bash, file symlinks require admin or developer-mode; directory junctions (`mklink /J`) don't.

- [ ] **Step 1: From the worktree root, create junctions for node_modules + venv.**

Run (from project root, the main checkout — not the worktree):
```bash
cmd //c "mklink /J .claude\worktrees\canvas-5-voice-routing\node_modules node_modules"
cmd //c "mklink /J .claude\worktrees\canvas-5-voice-routing\python-service\venv python-service\venv"
```
Expected: both print "Junction created for ... <<===>> ..."

- [ ] **Step 2: Verify junctions resolve.**

```bash
ls .claude/worktrees/canvas-5-voice-routing/node_modules/.bin | head -3
ls .claude/worktrees/canvas-5-voice-routing/python-service/venv/Scripts/python.exe
```
Expected: shows node_modules binaries + python.exe path exists.

- [ ] **Step 3: Install new Python deps via the shared venv.**

```bash
.claude/worktrees/canvas-5-voice-routing/python-service/venv/Scripts/python.exe -m pip install \
  anthropic>=0.69.0 \
  sentence-transformers>=3.0.0 \
  rapidfuzz>=3.9.0 \
  pytest-asyncio>=0.24.0
```
Expected: "Successfully installed ...". Note: sentence-transformers pulls torch CPU (~400 MB) on first install — that's a known one-time cost. If torch install fails (network/disk), proceed without it; `title_matcher` falls back to rapidfuzz-only.

- [ ] **Step 4: Run the existing baseline test suites in the worktree.**

```bash
cd .claude/worktrees/canvas-5-voice-routing
npm test 2>&1 | tail -20
python-service/venv/Scripts/python.exe -m pytest python-service/tests/ -q 2>&1 | tail -20
```
Expected: both pass (the canary + debug tests). If anything fails, that's pre-existing breakage — STOP and report, don't proceed.

- [ ] **Step 5: Commit setup (no code changes — junctions are local, not tracked).**

Junctions live outside git tracking. No commit needed for this task — just confirm baseline green before moving on. Skip the commit; subsequent tasks commit their own work.

---

### Task 2: Quick Inbox DB column + migration

**Files:**
- Modify: `python-service/database.py` (add column to schema + ALTER TABLE migration + `get_quick_inbox()` + delete guard)
- Test: `python-service/tests/test_quick_inbox.py` (DB-layer tests)

**Production-code escalation rule:** if the migration's reverse-rename, idempotency check, or other branch requires changing code OUTSIDE `database.py`, STOP and report `DONE_WITH_CONCERNS`.

- [ ] **Step 1: Write the failing migration tests.**

Create `python-service/tests/test_quick_inbox.py`:
```python
import os
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

# Point DB_PATH at a temp file BEFORE importing database, so init_db creates
# a fresh schema we can poke at without colliding with the user's real DB.
@pytest.fixture
def tmp_db(monkeypatch):
    tmp = Path(tempfile.mkdtemp()) / "test.db"
    monkeypatch.setenv("DEEN_NOTES_DB_OVERRIDE", str(tmp))
    import importlib
    import config
    importlib.reload(config)
    import database
    importlib.reload(database)
    yield database
    if tmp.exists():
        tmp.unlink()


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
```

- [ ] **Step 2: Run tests to verify they fail.**

```bash
cd .claude/worktrees/canvas-5-voice-routing
python-service/venv/Scripts/python.exe -m pytest python-service/tests/test_quick_inbox.py -v
```
Expected: 4 failures — column doesn't exist, `get_quick_inbox` / `create_quick_inbox` don't exist, `delete_note` succeeds (no guard yet).

- [ ] **Step 3: Add `DEEN_NOTES_DB_OVERRIDE` support to config + add column + helpers to database.**

In `python-service/config.py`, locate the existing `DB_PATH` definition and replace it with:
```python
import os
# DEEN_NOTES_DB_OVERRIDE is set by tests so they don't trash the real DB.
# Production launches use DEEN_NOTES_DATA_DIR (set by Electron) or fall through.
_override = os.environ.get("DEEN_NOTES_DB_OVERRIDE")
if _override:
    DB_PATH = _override
else:
    _data_dir = os.environ.get("DEEN_NOTES_DATA_DIR") or os.getcwd()
    DB_PATH = os.path.join(_data_dir, "noter.db")
```
(If `DB_PATH` already has this structure, keep it and only insert the override branch at the top.)

In `python-service/database.py`, inside `init_db()` after the existing `video_url` migration block, add:
```python
        # Quick Inbox singleton flag — set on the one special inbox note so
        # we can find it via SELECT and protect it from deletion.
        if "is_quick_inbox" not in columns:
            await db.execute(
                "ALTER TABLE notes ADD COLUMN is_quick_inbox INTEGER DEFAULT 0"
            )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_notes_quick_inbox "
            "ON notes(is_quick_inbox) WHERE is_quick_inbox = 1"
        )
```

Append two new functions at module bottom (above `_row_to_dict`):
```python
async def get_quick_inbox() -> dict | None:
    """Return the Quick Inbox note (singleton) or None if it doesn't exist yet."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM notes WHERE is_quick_inbox = 1 LIMIT 1"
        )
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None


async def create_quick_inbox() -> dict:
    """Create the Quick Inbox note. Caller (quick_inbox.ensure_quick_inbox)
    is responsible for the get-then-create guard to avoid two of them."""
    note_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    note = {
        "id": note_id,
        "title": "Quick Inbox",
        "content": "",
        "tags": json.dumps(["inbox"]),
        "source": "deen://quick-inbox",
        "video_url": "",
        "group_id": None,
        "is_quick_inbox": 1,
        "created_at": now,
        "updated_at": now,
    }
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO notes (id, title, content, tags, source, video_url, "
            "group_id, is_quick_inbox, created_at, updated_at) "
            "VALUES (:id, :title, :content, :tags, :source, :video_url, "
            ":group_id, :is_quick_inbox, :created_at, :updated_at)",
            note,
        )
        await db.commit()
    note["tags"] = ["inbox"]
    return note
```

Modify `delete_note` to refuse the Quick Inbox:
```python
async def delete_note(note_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT is_quick_inbox FROM notes WHERE id = ?", (note_id,)
        )
        row = await cursor.fetchone()
        if row and row["is_quick_inbox"]:
            return False  # protected — Quick Inbox is undeletable
        cursor = await db.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        await db.commit()
        return cursor.rowcount > 0
```

Also extend `_row_to_dict` to surface the flag (default 0 for legacy rows):
```python
def _row_to_dict(row) -> dict:
    d = dict(row)
    try:
        d["tags"] = json.loads(d.get("tags", "[]"))
    except (json.JSONDecodeError, TypeError):
        d["tags"] = []
    d["is_quick_inbox"] = int(d.get("is_quick_inbox") or 0)
    return d
```

- [ ] **Step 4: Run tests to verify they pass.**

```bash
python-service/venv/Scripts/python.exe -m pytest python-service/tests/test_quick_inbox.py -v
```
Expected: 4 passes.

- [ ] **Step 5: Commit.**

```bash
git add python-service/database.py python-service/config.py python-service/tests/test_quick_inbox.py
git commit -m "feat(voice): add Quick Inbox column, helpers, delete guard"
```

---

### Task 3: `quick_inbox.py` module + tests

**Files:**
- Create: `python-service/quick_inbox.py`
- Test: `python-service/tests/test_quick_inbox.py` (extend with module-level tests)

**Why a separate module:** keeps the singleton lifecycle (ensure-on-startup, lookup-with-cache, protection check) in one place callable from anywhere — routes.py, voice_routing, the eventual sidebar API.

- [ ] **Step 1: Extend `test_quick_inbox.py` with ensure-singleton tests.**

Append to `python-service/tests/test_quick_inbox.py`:
```python
@pytest.mark.asyncio
async def test_ensure_quick_inbox_creates_when_missing(tmp_db):
    await tmp_db.init_db()
    from quick_inbox import ensure_quick_inbox
    inbox = await ensure_quick_inbox()
    assert inbox["title"] == "Quick Inbox"
    assert inbox["is_quick_inbox"] == 1


@pytest.mark.asyncio
async def test_ensure_quick_inbox_idempotent(tmp_db):
    await tmp_db.init_db()
    from quick_inbox import ensure_quick_inbox
    first = await ensure_quick_inbox()
    second = await ensure_quick_inbox()
    assert first["id"] == second["id"]


@pytest.mark.asyncio
async def test_is_quick_inbox_id_matches(tmp_db):
    await tmp_db.init_db()
    from quick_inbox import ensure_quick_inbox, is_quick_inbox_id
    inbox = await ensure_quick_inbox()
    assert await is_quick_inbox_id(inbox["id"]) is True
    assert await is_quick_inbox_id("not-a-real-id") is False
```

- [ ] **Step 2: Run tests to verify they fail.**

```bash
python-service/venv/Scripts/python.exe -m pytest python-service/tests/test_quick_inbox.py -v -k "ensure or is_quick_inbox_id"
```
Expected: 3 failures — `quick_inbox` module doesn't exist.

- [ ] **Step 3: Create the module.**

Create `python-service/quick_inbox.py`:
```python
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

Identification: the database column `notes.is_quick_inbox` (added in Task 2)
is the source of truth. We DO NOT identify by title — users may rename
(though the UI doesn't expose that today) and we want to survive that.
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


async def is_quick_inbox_id(note_id: str | None) -> bool:
    """Fast check: is this note id the Quick Inbox?

    Uses the cached id when available; falls through to a DB lookup so we're
    correct even after a fresh process start (cache empty)."""
    if not note_id:
        return False
    if _cached_id is not None:
        return note_id == _cached_id
    inbox = await db.get_quick_inbox()
    if inbox is None:
        return False
    # Populate cache on the cold path.
    globals()["_cached_id"] = inbox["id"]
    return note_id == inbox["id"]


def get_cached_id() -> Optional[str]:
    """Synchronous read of the cached Quick Inbox id, for callers that
    already know ensure_quick_inbox() has run. Returns None on cold cache —
    callers should treat None as 'not yet ensured' and fall back gracefully."""
    return _cached_id
```

- [ ] **Step 4: Run tests to verify they pass.**

```bash
python-service/venv/Scripts/python.exe -m pytest python-service/tests/test_quick_inbox.py -v
```
Expected: 7 passes.

- [ ] **Step 5: Commit.**

```bash
git add python-service/quick_inbox.py python-service/tests/test_quick_inbox.py
git commit -m "feat(voice): quick_inbox.ensure singleton + id check"
```

---

### Task 4: `context_state.py` — foreground + last-capture state

**Files:**
- Create: `python-service/context_state.py`
- Test: `python-service/tests/test_context_state.py`

**Why:** voice routing needs two pieces of context the existing code doesn't track:
1. *Foreground / open-note id* — pushed from Electron via the new `/context` endpoint. Used as the no-qualifier default when Deen Notes is foregrounded with a note open.
2. *Last capture* — `{note_id, timestamp}` updated after every successful save. Used by the `"continue"` voice pattern (30-min window).

Mirrors the singleton-with-lock pattern from `target.py`.

- [ ] **Step 1: Write failing tests.**

Create `python-service/tests/test_context_state.py`:
```python
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


def test_last_capture_outside_window_returns_none(monkeypatch):
    """Pretend the last capture happened 31 minutes ago — the 30-min window
    should expire it and return None."""
    context_state.set_last_capture("note-id-1")
    stale = datetime.now(timezone.utc) - timedelta(minutes=31)
    # Patch the stored timestamp directly to simulate clock advance without
    # needing a fake-clock harness across the whole module.
    context_state._last_capture["timestamp"] = stale
    assert context_state.get_last_capture(window_seconds=30 * 60) is None
```

- [ ] **Step 2: Run tests to verify they fail.**

```bash
python-service/venv/Scripts/python.exe -m pytest python-service/tests/test_context_state.py -v
```
Expected: 7 failures (`context_state` doesn't exist).

- [ ] **Step 3: Create the module.**

Create `python-service/context_state.py`:
```python
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


def set_context(foreground: bool, open_note_id: Optional[str]) -> None:
    """Replace the context. Called from POST /context."""
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
```

- [ ] **Step 4: Run tests to verify they pass.**

```bash
python-service/venv/Scripts/python.exe -m pytest python-service/tests/test_context_state.py -v
```
Expected: 7 passes.

- [ ] **Step 5: Commit.**

```bash
git add python-service/context_state.py python-service/tests/test_context_state.py
git commit -m "feat(voice): context_state + last_capture singletons"
```

---

## Phase B — Voice routing core

### Task 5: Grammar parser

**Files:**
- Create: `python-service/voice_routing.py` (parser only; matcher + decision land in later tasks)
- Test: `python-service/tests/test_voice_routing.py`

**Why a regex parser, not the LLM:** the four patterns are short, prefix-anchored, case-insensitive, with very few legal variations. Regex catches 99% at zero cost and zero latency. LLM only enters via Haiku as a tiebreaker on the matcher side.

- [ ] **Step 1: Write failing parser tests.**

Create `python-service/tests/test_voice_routing.py`:
```python
import pytest

from voice_routing import parse_command, ParsedCommand


def test_no_qualifier_returns_inbox():
    p = parse_command("Take note: I had pizza for lunch.")
    assert p.kind == "inbox"
    assert p.qualifier is None
    assert p.content == "Take note: I had pizza for lunch."


def test_in_qualifier_matches_with_comma():
    p = parse_command("in Sapiens, the author argues humans love stories.")
    assert p.kind == "in"
    assert p.qualifier == "Sapiens"
    assert p.content == "the author argues humans love stories."


def test_in_qualifier_matches_without_comma():
    p = parse_command("in Sapiens the author argues humans love stories.")
    assert p.kind == "in"
    assert p.qualifier == "Sapiens"
    assert p.content.startswith("the author argues")


def test_in_qualifier_multi_word():
    p = parse_command("in Cooking Eggs, scramble at medium-low heat.")
    assert p.kind == "in"
    assert p.qualifier == "Cooking Eggs"
    assert p.content.startswith("scramble")


def test_in_qualifier_case_insensitive_prefix():
    p = parse_command("IN sapiens, lorem ipsum")
    assert p.kind == "in"
    assert p.qualifier.lower() == "sapiens"


def test_new_note_about_with_topic():
    p = parse_command("new note about cooking eggs, scramble at medium-low.")
    assert p.kind == "new"
    assert p.qualifier == "cooking eggs"
    assert p.content == "scramble at medium-low."


def test_new_note_about_without_comma():
    p = parse_command("new note about cooking eggs scramble at medium-low.")
    assert p.kind == "new"
    assert p.qualifier == "cooking eggs"


def test_continue_routes_to_recent():
    p = parse_command("continue, and another thing about that")
    assert p.kind == "continue"
    assert p.qualifier is None
    assert p.content == "and another thing about that"


def test_continue_without_comma():
    p = parse_command("continue and another thing")
    assert p.kind == "continue"
    assert p.content.startswith("and another thing")


def test_strips_leading_filler():
    """Whisper sometimes prefixes the command with 'uh' / 'um'. Strip those
    before parsing so 'uh, in Sapiens' still matches the 'in' pattern."""
    p = parse_command("uh, in Sapiens, hello")
    assert p.kind == "in"
    assert p.qualifier == "Sapiens"


def test_empty_string_is_inbox_with_empty_content():
    p = parse_command("")
    assert p.kind == "inbox"
    assert p.content == ""


def test_only_qualifier_no_content_routes_to_in_with_empty_body():
    """User pinned a note by voice: 'Hey Deen, in Sapiens.' — kind=in,
    empty content. Caller decides whether to treat this as a pin-only or
    to ask for content."""
    p = parse_command("in Sapiens.")
    assert p.kind == "in"
    assert p.qualifier == "Sapiens"
    assert p.content == ""
```

- [ ] **Step 2: Run tests to verify they fail.**

```bash
python-service/venv/Scripts/python.exe -m pytest python-service/tests/test_voice_routing.py -v
```
Expected: 12 failures (`voice_routing` doesn't exist).

- [ ] **Step 3: Create the parser.**

Create `python-service/voice_routing.py`:
```python
"""
Voice routing — parses the user's command transcript into a structured
destination decision.

Grammar (after "Hey Deen" wake word is stripped by the wake-word detector;
this module sees only the command transcript):

  [content]                              → kind=inbox, content=...
  in <name>[,] [content]                 → kind=in, qualifier=<name>, content=...
  new note about <topic>[,] [content]    → kind=new, qualifier=<topic>, content=...
  continue[,] [content]                  → kind=continue, content=...

Parsing is deliberately conservative: anything that doesn't match one of the
qualifier prefixes falls through to inbox. The matcher (Task 6) handles
mishearings of the qualifier name itself.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Optional

Kind = Literal["inbox", "in", "new", "continue"]


@dataclass(frozen=True)
class ParsedCommand:
    kind: Kind
    qualifier: Optional[str]  # for 'in' (note title) or 'new' (topic) — None otherwise
    content: str  # the body of what to capture (may be empty)


# Whisper preamble fillers — strip before parsing so 'uh, in Sapiens' parses
# as 'in Sapiens'. Anchored at the start.
_LEADING_FILLER_RE = re.compile(
    r"^(?:uh|um|er|so|ok|okay|hey|hey deen|deen)[\s,.\-]+",
    re.IGNORECASE,
)

# Match patterns in priority order: 'new note about' before 'in' (so "in"
# inside a longer "new note about" doesn't shortcut).
_NEW_RE = re.compile(
    r"^new\s+note\s+about\s+(.+?)(?:[,.]\s+|\s+(?=[A-Z])|$)",
    re.IGNORECASE,
)
_IN_RE = re.compile(
    r"^in\s+(.+?)(?:[,.]\s+|\s+(?=[a-z]{4,}\s)|$)",
    re.IGNORECASE,
)
_CONTINUE_RE = re.compile(
    r"^continue(?:[,.]\s+|\s+|$)",
    re.IGNORECASE,
)


def parse_command(text: str) -> ParsedCommand:
    """Parse a command transcript into a ParsedCommand.

    Robustness rules:
      - Leading filler ("uh", "um", "so") is stripped.
      - Case-insensitive matching at the prefix.
      - Comma after the qualifier is optional (Whisper sometimes drops it).
      - The qualifier ends at the first comma/period, OR a capitalized word
        boundary (heuristic for "in Sapiens The author..."), OR end of string.
      - Empty / unparseable input → kind=inbox with whatever's left.
    """
    if not text:
        return ParsedCommand(kind="inbox", qualifier=None, content="")

    stripped = text.strip()
    stripped = _LEADING_FILLER_RE.sub("", stripped).strip()

    # ── continue ──
    m = _CONTINUE_RE.match(stripped)
    if m:
        rest = stripped[m.end():].strip()
        return ParsedCommand(kind="continue", qualifier=None, content=rest)

    # ── new note about <topic> ──
    m = _NEW_RE.match(stripped)
    if m:
        qualifier = m.group(1).strip().rstrip(",.")
        rest = stripped[m.end():].strip()
        return ParsedCommand(kind="new", qualifier=qualifier, content=rest)

    # ── in <name> ──
    m = _IN_RE.match(stripped)
    if m:
        qualifier = m.group(1).strip().rstrip(",.")
        rest = stripped[m.end():].strip()
        return ParsedCommand(kind="in", qualifier=qualifier, content=rest)

    # ── fallthrough: inbox ──
    return ParsedCommand(kind="inbox", qualifier=None, content=stripped)
```

- [ ] **Step 4: Run tests to verify they pass.**

```bash
python-service/venv/Scripts/python.exe -m pytest python-service/tests/test_voice_routing.py -v
```
Expected: 12 passes. If `test_in_qualifier_multi_word` or `test_in_qualifier_matches_without_comma` fail because the heuristic boundary is off, adjust the lookahead in `_IN_RE` — typical issue is the `(?=[a-z]{4,}\s)` swallowing a valid second qualifier word. If you need to relax the boundary, document why and re-run. **Production-code escalation rule:** changes to anything OUTSIDE `voice_routing.py` to make these parser tests pass are NOT in scope — STOP if needed.

- [ ] **Step 5: Commit.**

```bash
git add python-service/voice_routing.py python-service/tests/test_voice_routing.py
git commit -m "feat(voice): grammar parser for 4-pattern routing"
```

---

### Task 6: `title_matcher.py` — fuzzy + optional embedding

**Files:**
- Create: `python-service/title_matcher.py`
- Test: `python-service/tests/test_title_matcher.py`

**Architecture:** rapidfuzz handles common string mishearings (Sapiens vs. Sapians). sentence-transformers handles paraphrase / semantic matches (cooking → Recipes) when available. The two scores combine via weighted average; missing embeddings → rapidfuzz-only. Returned candidates carry both raw scores so the caller can inspect.

- [ ] **Step 1: Write failing tests.**

Create `python-service/tests/test_title_matcher.py`:
```python
import pytest

from title_matcher import score_all, MatchResult


SAMPLE_NOTES = [
    {"id": "n1", "title": "Sapiens"},
    {"id": "n2", "title": "Sapiens chapter 2"},
    {"id": "n3", "title": "Cooking Eggs"},
    {"id": "n4", "title": "Recipes"},
    {"id": "n5", "title": "Weekly Standup"},
]


def test_exact_match_is_high_confidence():
    results = score_all("Sapiens", SAMPLE_NOTES)
    top = results[0]
    assert top.note_id == "n1"
    assert top.combined_score >= 0.95
    assert top.fuzzy_score >= 0.95


def test_mishearing_still_ranks_correct_note_first():
    """'Sapians' (mis-heard 'Sapiens') should still pick Sapiens, not unrelated."""
    results = score_all("Sapians", SAMPLE_NOTES)
    assert results[0].note_id == "n1"
    assert results[0].combined_score >= 0.75


def test_ambiguous_returns_both_close():
    """Two notes named 'Sapiens'/'Sapiens chapter 2' — both should score high
    and within a small epsilon of each other, signalling ambiguity to caller."""
    results = score_all("Sapiens", SAMPLE_NOTES)
    top2 = results[:2]
    assert {r.note_id for r in top2} == {"n1", "n2"}
    # The two top scores should be within 0.20 of each other.
    assert abs(top2[0].combined_score - top2[1].combined_score) < 0.20


def test_unrelated_input_low_score():
    results = score_all("Quantum Physics", SAMPLE_NOTES)
    assert results[0].combined_score < 0.60


def test_results_sorted_descending():
    results = score_all("Standup", SAMPLE_NOTES)
    for i in range(len(results) - 1):
        assert results[i].combined_score >= results[i + 1].combined_score


def test_empty_notes_returns_empty():
    assert score_all("anything", []) == []


def test_empty_query_returns_zero_scores():
    results = score_all("", SAMPLE_NOTES)
    assert all(r.combined_score == 0 for r in results)
```

- [ ] **Step 2: Run tests to verify they fail.**

```bash
python-service/venv/Scripts/python.exe -m pytest python-service/tests/test_title_matcher.py -v
```
Expected: 7 failures.

- [ ] **Step 3: Create the matcher.**

Create `python-service/title_matcher.py`:
```python
"""
Title matcher — ranks notes by similarity to a spoken qualifier.

Two scorers combine into one decision:
  - rapidfuzz token_set_ratio: fast, string-distance, catches mishearings
    ('Sapians' → 'Sapiens').
  - sentence-transformers cosine: semantic, catches paraphrases ('cooking
    notes' → 'Recipes'). OPTIONAL — if sentence-transformers isn't installed
    or fails to load, we silently fall back to rapidfuzz-only. The voice
    routing tier handles low-confidence outcomes by escalating to Haiku.

The combined score is a weighted average (rapidfuzz 0.6, embedding 0.4) so
exact-ish string matches dominate but semantic matches still surface.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from rapidfuzz import fuzz
from debug import debug


@dataclass(frozen=True)
class MatchResult:
    note_id: str
    title: str
    fuzzy_score: float       # 0..1
    embedding_score: float   # 0..1, or 0.0 if embedding unavailable
    combined_score: float    # 0..1


# Lazy module-level state for the embedding model. Loading torch + a 80MB
# model takes 2-5 seconds the first time, so we defer until first use.
_embedding_model = None
_embedding_load_attempted = False


def _get_embedding_model():
    """Lazy-load the sentence-transformers model. Returns None if unavailable
    (no install, no network, no disk — any of which we tolerate)."""
    global _embedding_model, _embedding_load_attempted
    if _embedding_load_attempted:
        return _embedding_model
    _embedding_load_attempted = True
    try:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2"
        )
        debug.log("matcher", "embedding model loaded")
    except (ImportError, OSError, RuntimeError) as e:
        debug.warn(
            "matcher",
            "embedding model unavailable — using rapidfuzz only",
            str(e),
        )
        _embedding_model = None
    return _embedding_model


def _fuzzy_score(query: str, title: str) -> float:
    """token_set_ratio handles word reordering and stop-word noise better than
    plain ratio, which matters for spoken titles like 'Cooking Eggs' vs.
    'eggs cooking'."""
    if not query or not title:
        return 0.0
    return fuzz.token_set_ratio(query, title) / 100.0


def _embedding_scores(query: str, titles: list[str]) -> list[float]:
    """Cosine-similarity scores for one query against many titles. Returns
    a list of 0..1 floats (negative similarities are clamped to 0)."""
    if not query or not titles:
        return [0.0] * len(titles)
    model = _get_embedding_model()
    if model is None:
        return [0.0] * len(titles)
    try:
        # Encode together so we benefit from batching.
        all_texts = [query] + titles
        embeddings = model.encode(all_texts, normalize_embeddings=True)
        query_vec = embeddings[0]
        title_vecs = embeddings[1:]
        # Dot product on normalized vectors == cosine similarity. Clamp to
        # [0, 1] — anti-correlated titles aren't useful as a "score".
        sims = (title_vecs @ query_vec).tolist()
        return [max(0.0, min(1.0, float(s))) for s in sims]
    except (RuntimeError, ValueError) as e:
        debug.warn("matcher", "embedding scoring failed", str(e))
        return [0.0] * len(titles)


def score_all(
    query: str,
    notes: Iterable[dict],
    fuzzy_weight: float = 0.6,
    embedding_weight: float = 0.4,
) -> list[MatchResult]:
    """Score every note's title against the query. Returns results sorted by
    combined_score descending."""
    notes_list = list(notes)
    if not notes_list:
        return []

    titles = [n.get("title") or "" for n in notes_list]
    emb_scores = _embedding_scores(query, titles)

    results = []
    for note, emb_score in zip(notes_list, emb_scores):
        title = note.get("title") or ""
        fuzzy = _fuzzy_score(query, title)
        # If embeddings are off, give fuzzy the full weight.
        if emb_score == 0.0 and _get_embedding_model() is None:
            combined = fuzzy
        else:
            combined = fuzzy * fuzzy_weight + emb_score * embedding_weight
        results.append(MatchResult(
            note_id=note["id"],
            title=title,
            fuzzy_score=fuzzy,
            embedding_score=emb_score,
            combined_score=combined,
        ))

    results.sort(key=lambda r: r.combined_score, reverse=True)
    return results
```

- [ ] **Step 4: Run tests to verify they pass.**

```bash
python-service/venv/Scripts/python.exe -m pytest python-service/tests/test_title_matcher.py -v
```
Expected: 7 passes. **Production-code escalation rule:** if making tests pass requires editing anything OUTSIDE `title_matcher.py`, STOP. (Exception: if sentence-transformers' model download fails inside a test environment, the test still passes because the matcher falls back to rapidfuzz — verify by checking `_embedding_model is None` in the failure branch.)

- [ ] **Step 5: Commit.**

```bash
git add python-service/title_matcher.py python-service/tests/test_title_matcher.py
git commit -m "feat(voice): title matcher (rapidfuzz + optional embedding)"
```

---

### Task 7: `voice_routing.route()` — local tier

**Files:**
- Modify: `python-service/voice_routing.py` (add `RoutingDecision` + `route_local()`)
- Modify: `python-service/tests/test_voice_routing.py` (extend with routing tests)

**Decision tiers** (this task only implements the LOCAL tier; Haiku fallback is Task 9):
1. `kind=inbox` → route to Quick Inbox (need its id passed in).
2. `kind=continue` → use `context_state.get_last_capture()`; if None → `needs_disambiguation`.
3. `kind=new` → `create_new` with the qualifier as the proposed title.
4. `kind=in` → `title_matcher.score_all(qualifier, notes)`:
   - top ≥ 0.85 AND (top - second) ≥ 0.15 → `existing` (high confidence)
   - top ≥ 0.70 → `needs_confirmation` ("did you mean Sapiens? yes/no")
   - top ≥ 0.50 AND multiple close → `needs_disambiguation` ("Sapiens chapter 1 or chapter 2?")
   - top < 0.50 → `no_match` ("no note called X — create one? yes/no")

The "needs_confirmation" / "needs_disambiguation" / "no_match" branches all surface the SAME `RoutingDecision` shape with `kind="needs_voice_followup"` and a different `question` + `candidates` field. The disambiguation loop (Task 12) handles them uniformly.

- [ ] **Step 1: Append failing routing tests.**

Append to `python-service/tests/test_voice_routing.py`:
```python
import pytest

from voice_routing import RoutingDecision, route_local, parse_command


QUICK_INBOX_ID = "quick-inbox-id-abc"

SAMPLE_NOTES = [
    {"id": "n1", "title": "Sapiens"},
    {"id": "n2", "title": "Sapiens chapter 2"},
    {"id": "n3", "title": "Cooking Eggs"},
    {"id": "n4", "title": "Recipes"},
]


def test_route_inbox_returns_quick_inbox():
    parsed = parse_command("Random thought to drop somewhere.")
    decision = route_local(parsed, SAMPLE_NOTES, QUICK_INBOX_ID, last_capture=None)
    assert decision.kind == "existing"
    assert decision.note_id == QUICK_INBOX_ID


def test_route_in_high_confidence_picks_top():
    parsed = parse_command("in Cooking Eggs, scramble at medium-low.")
    decision = route_local(parsed, SAMPLE_NOTES, QUICK_INBOX_ID, last_capture=None)
    assert decision.kind == "existing"
    assert decision.note_id == "n3"
    assert decision.content == "scramble at medium-low."


def test_route_in_ambiguous_multi_match():
    parsed = parse_command("in Sapiens, the author argues...")
    decision = route_local(parsed, SAMPLE_NOTES, QUICK_INBOX_ID, last_capture=None)
    # Two 'Sapiens' candidates → disambiguation
    assert decision.kind == "needs_voice_followup"
    titles = {c["title"] for c in decision.candidates}
    assert "Sapiens" in titles and "Sapiens chapter 2" in titles
    assert "Sapiens" in (decision.question or "")


def test_route_in_no_match_offers_creation():
    parsed = parse_command("in Quantum Physics, hello")
    decision = route_local(parsed, SAMPLE_NOTES, QUICK_INBOX_ID, last_capture=None)
    assert decision.kind == "needs_voice_followup"
    assert "Quantum Physics" in (decision.question or "")
    assert "create" in (decision.question or "").lower()


def test_route_new_returns_create_new_with_titlecase():
    parsed = parse_command("new note about cooking eggs, scramble at medium.")
    decision = route_local(parsed, SAMPLE_NOTES, QUICK_INBOX_ID, last_capture=None)
    assert decision.kind == "create_new"
    assert decision.proposed_title == "Cooking Eggs"
    assert decision.content == "scramble at medium."


def test_route_continue_uses_last_capture():
    parsed = parse_command("continue, and another thing.")
    last = {"note_id": "n4", "timestamp": None}  # timestamp ignored at this level
    decision = route_local(parsed, SAMPLE_NOTES, QUICK_INBOX_ID, last_capture=last)
    assert decision.kind == "existing"
    assert decision.note_id == "n4"


def test_route_continue_with_no_recent_capture_asks():
    parsed = parse_command("continue, hello")
    decision = route_local(parsed, SAMPLE_NOTES, QUICK_INBOX_ID, last_capture=None)
    assert decision.kind == "needs_voice_followup"
    assert "continue" in (decision.question or "").lower()
```

- [ ] **Step 2: Run tests to verify they fail.**

```bash
python-service/venv/Scripts/python.exe -m pytest python-service/tests/test_voice_routing.py::test_route_inbox_returns_quick_inbox python-service/tests/test_voice_routing.py::test_route_in_high_confidence_picks_top -v
```
Expected: failures — `route_local` doesn't exist.

- [ ] **Step 3: Extend `voice_routing.py` with `RoutingDecision` + `route_local`.**

Append to `python-service/voice_routing.py`:
```python
# ─── Routing decision ──────────────────────────────────────────────────────

from typing import Optional, List, Dict
from dataclasses import field

import title_matcher

# Decision-tier thresholds. These are tuned for short titles + voice
# transcription noise; revisit if Abed reports too-many false positives or
# too-many disambiguation prompts in real use.
HIGH_CONFIDENCE_MIN = 0.85
HIGH_CONFIDENCE_GAP = 0.15
CONFIRM_MIN = 0.70
DISAMBIGUATE_MIN = 0.50


@dataclass(frozen=True)
class RoutingDecision:
    """The outcome of routing a parsed command against current notes + state.

    kind:
      - "existing"               → save to note_id (Quick Inbox, pinned, or matched)
      - "create_new"             → caller creates a note with proposed_title
      - "needs_voice_followup"   → caller speaks `question` and listens; handles
                                   yes/no/named answer via parse_response()
    """
    kind: str
    content: str
    note_id: Optional[str] = None
    proposed_title: Optional[str] = None
    candidates: List[Dict] = field(default_factory=list)  # [{id, title, score}, ...]
    question: Optional[str] = None
    confidence: str = "high"  # 'high' | 'medium' | 'low'


def _titlecase_topic(topic: str) -> str:
    """Convert 'cooking eggs' → 'Cooking Eggs' for new-note titles."""
    return " ".join(w.capitalize() for w in topic.split())


def route_local(
    parsed: ParsedCommand,
    notes: list[dict],
    quick_inbox_id: str,
    last_capture: Optional[dict],
) -> RoutingDecision:
    """Local-only routing: parser + title matcher, no Haiku.

    Caller is responsible for filtering Quick Inbox OUT of the `notes` list
    when scoring 'in <name>' — we don't want fuzzy-matching the inbox itself.
    Quick Inbox enters as the explicit no-qualifier destination only.
    """
    # ── inbox ──
    if parsed.kind == "inbox":
        return RoutingDecision(
            kind="existing",
            note_id=quick_inbox_id,
            content=parsed.content,
            confidence="high",
        )

    # ── continue ──
    if parsed.kind == "continue":
        if last_capture and last_capture.get("note_id"):
            return RoutingDecision(
                kind="existing",
                note_id=last_capture["note_id"],
                content=parsed.content,
                confidence="high",
            )
        return RoutingDecision(
            kind="needs_voice_followup",
            content=parsed.content,
            question=(
                "Nothing to continue — you haven't captured recently. "
                "Name a note, or say inbox."
            ),
            candidates=[],
            confidence="low",
        )

    # ── new ──
    if parsed.kind == "new":
        title = _titlecase_topic(parsed.qualifier or "Untitled")
        return RoutingDecision(
            kind="create_new",
            proposed_title=title,
            content=parsed.content,
            confidence="high",
        )

    # ── in <name> ──  (only remaining kind)
    if not parsed.qualifier:
        return RoutingDecision(
            kind="existing",
            note_id=quick_inbox_id,
            content=parsed.content,
            confidence="low",
        )

    # Score against notes EXCLUDING Quick Inbox itself.
    candidates_pool = [n for n in notes if n.get("id") != quick_inbox_id]
    if not candidates_pool:
        return RoutingDecision(
            kind="needs_voice_followup",
            content=parsed.content,
            question=(
                f"No note called {parsed.qualifier}. "
                "Create one? Say yes or no."
            ),
            candidates=[],
            confidence="low",
        )

    ranked = title_matcher.score_all(parsed.qualifier, candidates_pool)
    if not ranked:
        return RoutingDecision(
            kind="needs_voice_followup",
            content=parsed.content,
            question=f"No notes to match {parsed.qualifier}. Say a note name.",
            confidence="low",
        )

    top = ranked[0]
    second_score = ranked[1].combined_score if len(ranked) > 1 else 0.0
    gap = top.combined_score - second_score

    # High confidence: clear winner.
    if top.combined_score >= HIGH_CONFIDENCE_MIN and gap >= HIGH_CONFIDENCE_GAP:
        return RoutingDecision(
            kind="existing",
            note_id=top.note_id,
            content=parsed.content,
            confidence="high",
        )

    # Mid confidence, no clear second: ask to confirm.
    if top.combined_score >= CONFIRM_MIN and gap >= HIGH_CONFIDENCE_GAP:
        return RoutingDecision(
            kind="needs_voice_followup",
            content=parsed.content,
            candidates=[{"id": top.note_id, "title": top.title,
                          "score": top.combined_score}],
            question=f"Did you mean {top.title}? Say yes or no.",
            confidence="medium",
        )

    # Two or more close candidates: ask which.
    close_candidates = [
        r for r in ranked
        if r.combined_score >= DISAMBIGUATE_MIN
        and (top.combined_score - r.combined_score) < HIGH_CONFIDENCE_GAP
    ]
    if len(close_candidates) >= 2:
        names = " or ".join(c.title for c in close_candidates[:3])
        return RoutingDecision(
            kind="needs_voice_followup",
            content=parsed.content,
            candidates=[
                {"id": c.note_id, "title": c.title, "score": c.combined_score}
                for c in close_candidates[:5]
            ],
            question=f"{names}? Say which.",
            confidence="medium",
        )

    # Single mid-low score, no close runner-up: confirm anyway.
    if top.combined_score >= DISAMBIGUATE_MIN:
        return RoutingDecision(
            kind="needs_voice_followup",
            content=parsed.content,
            candidates=[{"id": top.note_id, "title": top.title,
                          "score": top.combined_score}],
            question=f"Did you mean {top.title}? Say yes or no.",
            confidence="medium",
        )

    # No match at all.
    return RoutingDecision(
        kind="needs_voice_followup",
        content=parsed.content,
        question=(
            f"No note called {parsed.qualifier}. "
            "Create one? Say yes or no."
        ),
        confidence="low",
    )
```

- [ ] **Step 4: Run all voice routing tests.**

```bash
python-service/venv/Scripts/python.exe -m pytest python-service/tests/test_voice_routing.py -v
```
Expected: 19 passes (12 parser + 7 routing).

- [ ] **Step 5: Commit.**

```bash
git add python-service/voice_routing.py python-service/tests/test_voice_routing.py
git commit -m "feat(voice): RoutingDecision + local-tier routing (parser + matcher)"
```

---

### Task 8: `haiku_client.py` — Haiku 4.5 fallback

**Files:**
- Create: `python-service/haiku_client.py`
- Test: `python-service/tests/test_haiku_client.py`

**Why Haiku 4.5:** spec says local-first, Haiku for ambiguity. Haiku 4.5 (model id `claude-haiku-4-5`) is the cheapest current Anthropic model — fast, ~$0.0001/call on short prompts. The model decides between candidate titles given the spoken qualifier + utterance content for context.

The client is intentionally thin: one function, `pick_best(query, candidates, content)`, returns `{"note_id": str | None, "confidence": "high"|"low"}` or None on any error (network, missing key, parse failure). All errors degrade gracefully — the caller falls back to disambiguation.

- [ ] **Step 1: Write failing tests.**

Create `python-service/tests/test_haiku_client.py`:
```python
from unittest.mock import MagicMock, patch

import pytest

import haiku_client


@patch("haiku_client._get_client")
def test_pick_best_returns_chosen_id(mock_get_client):
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


@patch("haiku_client._get_client")
def test_pick_best_returns_none_on_invalid_json(mock_get_client):
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text="this is not json")]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_msg
    mock_get_client.return_value = fake_client

    result = haiku_client.pick_best(
        query="x", candidates=[{"id": "n1", "title": "Sapiens"}], content="hi"
    )
    assert result is None


@patch("haiku_client._get_client", side_effect=RuntimeError("network down"))
def test_pick_best_returns_none_on_exception(mock_get_client):
    result = haiku_client.pick_best(
        query="x", candidates=[{"id": "n1", "title": "Sapiens"}], content="hi"
    )
    assert result is None


@patch("haiku_client._get_client")
def test_pick_best_returns_none_when_no_candidates(mock_get_client):
    result = haiku_client.pick_best(query="x", candidates=[], content="hi")
    assert result is None
    mock_get_client.assert_not_called()


def test_pick_best_skips_when_no_key(monkeypatch):
    """If ANTHROPIC_API_KEY is absent, pick_best must not even attempt a call.
    Returns None so the caller can fall through to disambiguation."""
    monkeypatch.setattr(haiku_client, "_get_api_key", lambda: None)
    result = haiku_client.pick_best(
        query="x", candidates=[{"id": "n1", "title": "Sapiens"}], content="hi"
    )
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail.**

```bash
python-service/venv/Scripts/python.exe -m pytest python-service/tests/test_haiku_client.py -v
```
Expected: 5 failures — module doesn't exist.

- [ ] **Step 3: Create the client.**

Create `python-service/haiku_client.py`:
```python
"""
Anthropic Claude Haiku 4.5 — fallback tie-breaker for voice routing.

Local matcher (rapidfuzz + embeddings) handles 95% of voice routing
unambiguously. When local can't decide — multiple close candidates, or a
borderline mishearing — this client asks Haiku to pick.

Design:
  - Cheap (~$0.0001/call), fast (~300ms p50).
  - Graceful skip: missing key, network down, malformed response → return
    None. The caller (voice_routing.route) treats None as "fall through to
    disambiguation loop", which is the right behavior either way.
  - Structured output via system prompt + JSON-only request. We don't use
    tool-use because the response is one tiny JSON object — over-engineered
    for this case.
"""
from __future__ import annotations

import json
import os
from typing import Optional

from debug import debug

MODEL_ID = "claude-haiku-4-5"  # Floating alias; pin to claude-haiku-4-5-20251001 if drift becomes an issue.
MAX_TOKENS = 80


def _get_api_key() -> Optional[str]:
    """Read the key fresh each call so a settings-runtime update propagates
    without restarting the service."""
    return os.environ.get("ANTHROPIC_API_KEY") or None


_client_cache = {"key": None, "client": None}


def _get_client():
    """Lazy + cached Anthropic client. Rebuilt if the API key rotates."""
    key = _get_api_key()
    if not key:
        return None
    if _client_cache["key"] == key and _client_cache["client"] is not None:
        return _client_cache["client"]
    from anthropic import Anthropic
    client = Anthropic(api_key=key)
    _client_cache["key"] = key
    _client_cache["client"] = client
    return client


_SYSTEM_PROMPT = (
    "You disambiguate a spoken note-routing command. Given the user's spoken "
    "qualifier, what they actually want to capture, and a list of candidate "
    "note titles, pick which note they meant.\n\n"
    "Return ONLY valid JSON: {\"note_id\": \"<id from candidates>\", "
    "\"confidence\": \"high\"|\"low\"}. If no candidate matches with "
    "reasonable confidence, return {\"note_id\": null, \"confidence\": \"low\"}.\n\n"
    "No prose. No code fences. JSON only."
)


def pick_best(
    query: str,
    candidates: list[dict],
    content: str,
) -> Optional[dict]:
    """Ask Haiku to pick the best-matching note from `candidates`.

    Returns {"note_id": str | None, "confidence": "high"|"low"} on success,
    None on any failure (no key, network error, parse failure, empty input).
    """
    if not candidates:
        return None
    if not _get_api_key():
        return None

    try:
        client = _get_client()
        if client is None:
            return None

        candidate_lines = "\n".join(
            f"- id={c['id']}: {c.get('title') or ''}" for c in candidates
        )
        user_message = (
            f"Spoken qualifier: {query!r}\n"
            f"Captured content: {content!r}\n"
            f"Candidates:\n{candidate_lines}"
        )

        resp = client.messages.create(
            model=MODEL_ID,
            max_tokens=MAX_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        # Concatenate any text blocks (usually just one).
        raw = "".join(
            getattr(block, "text", "") for block in (resp.content or [])
        ).strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = json.loads(raw)

        if not isinstance(parsed, dict):
            return None
        note_id = parsed.get("note_id")
        if note_id is not None and not any(c["id"] == note_id for c in candidates):
            # Hallucinated id — refuse and downgrade.
            return None
        confidence = parsed.get("confidence")
        if confidence not in ("high", "low"):
            confidence = "low"
        return {"note_id": note_id, "confidence": confidence}

    except (json.JSONDecodeError, ValueError, KeyError) as e:
        debug.warn("haiku", "parse failure", str(e))
        return None
    except Exception as e:  # noqa: BLE001 — Anthropic raises various subclasses; degrade for all
        debug.warn("haiku", "API call failed", str(e))
        return None
```

- [ ] **Step 4: Run tests.**

```bash
python-service/venv/Scripts/python.exe -m pytest python-service/tests/test_haiku_client.py -v
```
Expected: 5 passes.

- [ ] **Step 5: Commit.**

```bash
git add python-service/haiku_client.py python-service/tests/test_haiku_client.py
git commit -m "feat(voice): Haiku 4.5 fallback client with graceful skip"
```

---

### Task 9: Wire Haiku into `voice_routing.route()`

**Files:**
- Modify: `python-service/voice_routing.py` (add `route()` that wraps `route_local` + Haiku fallback)
- Modify: `python-service/tests/test_voice_routing.py` (extend with route() tests)

**Logic:** if `route_local` returns `needs_voice_followup` AND we have at least one candidate AND we have a Haiku key, call Haiku. If Haiku returns high-confidence with a real candidate id, upgrade the decision to `kind="existing"`. Otherwise pass through the original decision unchanged.

- [ ] **Step 1: Append failing route() tests.**

Append to `python-service/tests/test_voice_routing.py`:
```python
from unittest.mock import patch

from voice_routing import route


@patch("voice_routing.haiku_client.pick_best")
def test_route_passes_through_high_confidence_unchanged(mock_haiku):
    parsed = parse_command("in Cooking Eggs, scramble.")
    decision = route(parsed, SAMPLE_NOTES, QUICK_INBOX_ID, last_capture=None)
    assert decision.kind == "existing"
    # High-confidence local match — Haiku should NOT be called.
    mock_haiku.assert_not_called()


@patch("voice_routing.haiku_client.pick_best",
       return_value={"note_id": "n1", "confidence": "high"})
def test_route_promotes_ambiguous_when_haiku_confident(mock_haiku):
    parsed = parse_command("in Sapiens, the author argues...")
    decision = route(parsed, SAMPLE_NOTES, QUICK_INBOX_ID, last_capture=None)
    assert decision.kind == "existing"
    assert decision.note_id == "n1"
    mock_haiku.assert_called_once()


@patch("voice_routing.haiku_client.pick_best", return_value=None)
def test_route_keeps_voice_followup_when_haiku_returns_none(mock_haiku):
    parsed = parse_command("in Sapiens, the author argues...")
    decision = route(parsed, SAMPLE_NOTES, QUICK_INBOX_ID, last_capture=None)
    assert decision.kind == "needs_voice_followup"
    assert "Sapiens" in (decision.question or "")


@patch("voice_routing.haiku_client.pick_best",
       return_value={"note_id": None, "confidence": "low"})
def test_route_keeps_voice_followup_when_haiku_says_unknown(mock_haiku):
    parsed = parse_command("in Sapiens, the author argues...")
    decision = route(parsed, SAMPLE_NOTES, QUICK_INBOX_ID, last_capture=None)
    assert decision.kind == "needs_voice_followup"


@patch("voice_routing.haiku_client.pick_best")
def test_route_skips_haiku_for_no_match(mock_haiku):
    """Empty candidates → no point asking Haiku; the user said a name we have
    no notes for at all."""
    parsed = parse_command("in Quantum Physics, hello")
    decision = route(parsed, SAMPLE_NOTES, QUICK_INBOX_ID, last_capture=None)
    assert decision.kind == "needs_voice_followup"
    # No candidates were close enough to warrant a Haiku call.
    if mock_haiku.called:
        call_args = mock_haiku.call_args
        candidates = call_args.kwargs.get("candidates") or call_args.args[1]
        assert candidates == []  # only allowed if called with empty list
```

- [ ] **Step 2: Run tests to verify they fail.**

```bash
python-service/venv/Scripts/python.exe -m pytest python-service/tests/test_voice_routing.py::test_route_passes_through_high_confidence_unchanged -v
```
Expected: failure — `route` doesn't exist.

- [ ] **Step 3: Append `route()` to `voice_routing.py`.**

```python
import haiku_client


def route(
    parsed: ParsedCommand,
    notes: list[dict],
    quick_inbox_id: str,
    last_capture: Optional[dict],
) -> RoutingDecision:
    """Full routing: local tier first, Haiku fallback for ambiguous results
    with at least one candidate.

    The Haiku fallback ONLY runs for `needs_voice_followup` with candidates,
    not for empty/no-match cases (no point asking Haiku to pick from nothing).
    """
    decision = route_local(parsed, notes, quick_inbox_id, last_capture)

    # Only escalate to Haiku for ambiguous-with-candidates.
    if decision.kind != "needs_voice_followup" or not decision.candidates:
        return decision

    haiku_result = haiku_client.pick_best(
        query=parsed.qualifier or "",
        candidates=decision.candidates,
        content=decision.content,
    )
    if not haiku_result:
        return decision  # graceful no-op — disambiguation loop will run
    if haiku_result.get("confidence") != "high":
        return decision
    note_id = haiku_result.get("note_id")
    if not note_id:
        return decision
    # Haiku is confident — promote to a direct route.
    return RoutingDecision(
        kind="existing",
        note_id=note_id,
        content=decision.content,
        confidence="high",
    )
```

- [ ] **Step 4: Run all tests.**

```bash
python-service/venv/Scripts/python.exe -m pytest python-service/tests/test_voice_routing.py -v
```
Expected: 24 passes (12 parser + 7 local + 5 route).

- [ ] **Step 5: Commit.**

```bash
git add python-service/voice_routing.py python-service/tests/test_voice_routing.py
git commit -m "feat(voice): Haiku tiebreaker on top of local routing"
```

---

## Phase C — Disambiguation + TTS

### Task 10: `tts_client.py` — graceful no-op TTS

**Files:**
- Create: `python-service/tts_client.py`
- Test: `python-service/tests/test_tts_client.py`

**Spec:** call Sub-project 4's `/tts/say?text=...`. Today that endpoint doesn't exist. Our client MUST:
- Try the call with a short timeout (2s — TTS should be fast or skip).
- Swallow 404 + connection errors + timeouts silently. No log spam.
- Never block the caller for more than the timeout, even on slow networks.

- [ ] **Step 1: Write failing tests.**

Create `python-service/tests/test_tts_client.py`:
```python
from unittest.mock import patch, MagicMock

import tts_client


def test_say_no_op_on_404():
    fake_response = MagicMock()
    fake_response.status = 404
    with patch("tts_client._http_get", return_value=fake_response):
        # Should not raise.
        tts_client.say("Saved to Quick Inbox")


def test_say_no_op_on_connection_error():
    with patch("tts_client._http_get", side_effect=ConnectionError("nope")):
        tts_client.say("Saved to Quick Inbox")  # no raise


def test_say_no_op_on_timeout():
    with patch("tts_client._http_get", side_effect=TimeoutError("slow")):
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
    # & must be encoded, otherwise it'd be parsed as a query separator
    assert "%26" in captured["url"] or "&" not in captured["url"].split("?text=")[1]
```

- [ ] **Step 2: Run tests to verify they fail.**

```bash
python-service/venv/Scripts/python.exe -m pytest python-service/tests/test_tts_client.py -v
```
Expected: 5 failures.

- [ ] **Step 3: Create the client.**

Create `python-service/tts_client.py`:
```python
"""
TTS hear-back client — speaks confirmations to the user after a capture.

Talks to Sub-project 4's /tts/say endpoint when present. Until that ships,
every call is a no-op (404 swallowed). Built so production code can call
say() unconditionally without conditional branches.

Design notes:
  - GET, not POST: matches the spec's `/tts/say?text=...` shape; the endpoint
    is read-only effectful (synthesize + play locally).
  - 2-second timeout: TTS must feel instant or not happen. A slow TTS path
    is worse than no TTS — it backs up the wake-word lock.
  - Failures are silent and warn-only-once-per-session via a flag, so a
    user without Sub-project 4 doesn't see noise on every capture.
"""
from __future__ import annotations

import http.client
import urllib.parse
from typing import Optional

from debug import debug

TTS_HOST = "127.0.0.1"
TTS_PORT = 8765  # same FastAPI port; endpoint may live under a sub-router
TTS_PATH = "/tts/say"
TIMEOUT_SEC = 2.0

_warned = False


def _http_get(url: str, timeout: float) -> http.client.HTTPResponse:
    """Thin GET wrapper. Split out so tests can mock without going to network."""
    parsed = urllib.parse.urlparse(url)
    conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=timeout)
    conn.request("GET", parsed.path + ("?" + parsed.query if parsed.query else ""))
    return conn.getresponse()


def say(text: str) -> None:
    """Speak `text` via the Python service's TTS endpoint, if available.

    Silently no-ops if the endpoint is missing or unreachable. Never raises."""
    global _warned
    if not text:
        return
    qs = urllib.parse.urlencode({"text": text})
    url = f"http://{TTS_HOST}:{TTS_PORT}{TTS_PATH}?{qs}"
    try:
        resp = _http_get(url, timeout=TIMEOUT_SEC)
        if resp.status == 404 and not _warned:
            debug.log("tts", "/tts/say not present (Sub-project 4 not merged) — silencing")
            _warned = True
    except (ConnectionError, TimeoutError, OSError):
        # Network blip or service restart — drop the audible confirmation
        # rather than blocking the save path.
        return
```

- [ ] **Step 4: Run tests.**

```bash
python-service/venv/Scripts/python.exe -m pytest python-service/tests/test_tts_client.py -v
```
Expected: 5 passes.

- [ ] **Step 5: Commit.**

```bash
git add python-service/tts_client.py python-service/tests/test_tts_client.py
git commit -m "feat(voice): TTS hear-back client with graceful no-op"
```

---

### Task 11: Response parser (yes/no/named match)

**Files:**
- Modify: `python-service/voice_routing.py` (add `parse_response()`)
- Modify: `python-service/tests/test_voice_routing.py` (extend)

**Usage flow:** disambiguation loop speaks "Did you mean Sapiens? Yes or no" → records user reply → transcribes → calls `parse_response(reply, candidates)` → gets one of: `{"kind": "yes"}`, `{"kind": "no"}`, `{"kind": "named", "note_id": ...}`, `{"kind": "unclear"}`.

- [ ] **Step 1: Append failing tests.**

Append to `python-service/tests/test_voice_routing.py`:
```python
from voice_routing import parse_response


def test_parse_response_yes_variants():
    for text in ["yes", "Yes", "yeah", "yep", "yup", "sure", "ok",
                  "okay", "confirmed", "correct"]:
        r = parse_response(text, candidates=[])
        assert r["kind"] == "yes", f"failed for {text!r}"


def test_parse_response_no_variants():
    for text in ["no", "No", "nope", "nah", "negative", "wrong"]:
        r = parse_response(text, candidates=[])
        assert r["kind"] == "no", f"failed for {text!r}"


def test_parse_response_named_matches_candidate():
    candidates = [
        {"id": "n1", "title": "Sapiens chapter 1"},
        {"id": "n2", "title": "Sapiens chapter 2"},
    ]
    r = parse_response("chapter two", candidates=candidates)
    assert r["kind"] == "named"
    assert r["note_id"] == "n2"


def test_parse_response_named_exact_title():
    candidates = [{"id": "n1", "title": "Cooking Eggs"}]
    r = parse_response("Cooking Eggs", candidates=candidates)
    assert r["kind"] == "named"
    assert r["note_id"] == "n1"


def test_parse_response_unclear_returns_unclear():
    r = parse_response("uhhh I don't know", candidates=[])
    assert r["kind"] == "unclear"


def test_parse_response_empty_is_unclear():
    r = parse_response("", candidates=[])
    assert r["kind"] == "unclear"


def test_parse_response_named_over_yes_when_both_present():
    """User says 'yes Sapiens chapter 2' — name wins, more specific."""
    candidates = [{"id": "n2", "title": "Sapiens chapter 2"}]
    r = parse_response("yes Sapiens chapter 2", candidates=candidates)
    assert r["kind"] == "named"
    assert r["note_id"] == "n2"
```

- [ ] **Step 2: Run tests to verify they fail.**

```bash
python-service/venv/Scripts/python.exe -m pytest python-service/tests/test_voice_routing.py -k "parse_response" -v
```
Expected: 7 failures.

- [ ] **Step 3: Append `parse_response` to `voice_routing.py`.**

```python
# ─── Response parsing (disambiguation loop) ────────────────────────────────

_YES_WORDS = {
    "yes", "yeah", "yep", "yup", "ok", "okay", "sure", "confirmed",
    "correct", "affirmative", "yes please", "right",
}
_NO_WORDS = {
    "no", "nope", "nah", "negative", "wrong", "incorrect",
}


def parse_response(text: str, candidates: list[dict]) -> dict:
    """Parse a yes/no/named answer from a spoken disambiguation reply.

    Returns one of:
      {"kind": "yes"}
      {"kind": "no"}
      {"kind": "named", "note_id": "...", "title": "..."}
      {"kind": "unclear"}

    Named match wins over yes — if the user says "yes Sapiens chapter 2",
    they're naming a candidate, not just confirming. The candidate list is
    typically 1-3 items deep, so we try fuzzy match against each and accept
    a threshold ≥ 0.55 (lower than the routing threshold because the user
    is choosing from a known short list).
    """
    if not text or not text.strip():
        return {"kind": "unclear"}

    cleaned = text.strip().lower().rstrip(".!?")

    # Try named match first — fuzzy against each candidate title.
    if candidates:
        best = None
        best_score = 0.0
        for c in candidates:
            score = title_matcher._fuzzy_score(cleaned, (c.get("title") or "").lower())
            if score > best_score:
                best_score = score
                best = c
        if best and best_score >= 0.55:
            return {
                "kind": "named",
                "note_id": best["id"],
                "title": best.get("title") or "",
            }

    # Yes / no detection — match individual words or short phrases.
    tokens = set(cleaned.replace(",", " ").split())
    if tokens & _YES_WORDS or cleaned in _YES_WORDS:
        return {"kind": "yes"}
    if tokens & _NO_WORDS or cleaned in _NO_WORDS:
        return {"kind": "no"}

    return {"kind": "unclear"}
```

- [ ] **Step 4: Run tests.**

```bash
python-service/venv/Scripts/python.exe -m pytest python-service/tests/test_voice_routing.py -v
```
Expected: 31 passes.

- [ ] **Step 5: Commit.**

```bash
git add python-service/voice_routing.py python-service/tests/test_voice_routing.py
git commit -m "feat(voice): parse_response for yes/no/named disambiguation"
```

---

### Task 12: Disambiguation listen loop

**Files:**
- Modify: `python-service/main.py` (add `run_disambiguation_loop`)
- Modify: `python-service/note_generator.py` (not yet — wiring happens in Task 14)

**Loop algorithm:**
1. Speak the question via `tts_client.say(decision.question)`.
2. `broadcast({"type": "status", "status": "command"})` so the bubble shows the listening UI.
3. `mic_listener.record_command()` → audio bytes.
4. Transcribe via `ai_client.transcribe_audio(wav, False)`.
5. `voice_routing.parse_response(transcript, decision.candidates)` → result.
6. Map result back to a new RoutingDecision:
   - `yes` + decision is "Did you mean X?" → route to X.
   - `yes` + decision is "Create X?" → create new with X as title.
   - `no` → fall through to Quick Inbox with audible "Saved to Quick Inbox — try again."
   - `named` → route to that candidate.
   - `unclear` → loop once more (max 2 attempts), then Quick Inbox.

- [ ] **Step 1: Add `run_disambiguation_loop` to `main.py`.**

In `python-service/main.py`, insert ABOVE `on_wake_word_detected`:
```python
from typing import Optional

import tts_client
import voice_routing
import ai_client
from mic_listener import record_command
from resampler import audio_to_wav_bytes

MAX_DISAMBIGUATION_RETRIES = 1  # one extra attempt after the first miss


def run_disambiguation_loop(
    decision: voice_routing.RoutingDecision,
    quick_inbox_id: str,
) -> voice_routing.RoutingDecision:
    """Run the voice-only disambiguation loop until we have a routable decision
    or we run out of retries (then fall through to Quick Inbox).

    `decision` must be kind=needs_voice_followup. The returned decision is
    always either kind=existing or kind=create_new — caller can save without
    additional prompting.
    """
    if decision.kind != "needs_voice_followup":
        return decision

    current = decision
    for attempt in range(MAX_DISAMBIGUATION_RETRIES + 1):
        tts_client.say(current.question or "Which note?")
        _broadcast_sync({"type": "status", "status": "command"})

        try:
            reply_audio = record_command()
        except (OSError, RuntimeError) as e:
            debug.error("Disamb", "mic failed mid-loop", e)
            break

        if reply_audio is None or len(reply_audio) == 0:
            debug.warn("Disamb", "no reply, retrying" if attempt == 0 else "still no reply")
            continue

        try:
            wav = audio_to_wav_bytes(reply_audio)
            transcript = ai_client.transcribe_audio(wav, with_speakers=False) or ""
        except (OSError, RuntimeError, ValueError) as e:
            debug.warn("Disamb", "transcription failed", e)
            continue

        debug.log("Disamb", "reply", transcript[:100])
        result = voice_routing.parse_response(transcript, current.candidates)

        if result["kind"] == "named":
            return voice_routing.RoutingDecision(
                kind="existing",
                note_id=result["note_id"],
                content=current.content,
                confidence="medium",
            )
        if result["kind"] == "yes":
            # If question was 'create X?' → create new; if 'Did you mean X?' → route to X.
            if current.candidates:
                return voice_routing.RoutingDecision(
                    kind="existing",
                    note_id=current.candidates[0]["id"],
                    content=current.content,
                    confidence="medium",
                )
            # No candidates → it was the 'no match — create one?' prompt.
            # Extract proposed title from the question text.
            #   "No note called Sapiens. Create one? Say yes or no." → "Sapiens"
            import re
            m = re.search(r"No note called (.+?)\.", current.question or "")
            title = m.group(1) if m else "Untitled Note"
            return voice_routing.RoutingDecision(
                kind="create_new",
                proposed_title=title.title(),
                content=current.content,
                confidence="medium",
            )
        if result["kind"] == "no":
            # User rejected the suggestion. Stop looping; fall through.
            break
        # unclear → next iteration (if any retries left)

    # Final fallback: Quick Inbox with a softer audible.
    tts_client.say("Saved to Quick Inbox — couldn't tell where you meant.")
    return voice_routing.RoutingDecision(
        kind="existing",
        note_id=quick_inbox_id,
        content=current.content,
        confidence="low",
    )
```

- [ ] **Step 2: Smoke-test the import (no test harness for the audio loop — it'd need a fake mic).**

```bash
python-service/venv/Scripts/python.exe -c "from main import run_disambiguation_loop; print('ok')"
```
Expected: "ok". A circular-import error here means we need to move imports inside the function — restructure if so.

- [ ] **Step 3: Commit.**

```bash
git add python-service/main.py
git commit -m "feat(voice): disambiguation listen loop (mic→transcript→retry)"
```

---

## Phase D — Wiring

### Task 13: Routes — `/context` endpoint + Quick Inbox bootstrap + delete protection

**Files:**
- Modify: `python-service/routes.py`

The DB delete-guard already lives in `database.delete_note` (Task 2). The route handler needs to surface that as HTTP 409 when it fires. The `/context` endpoint pair (GET + POST) mirrors `/target`. Startup gets one more call: `await ensure_quick_inbox()`.

- [ ] **Step 1: Add `/context` endpoints + Quick Inbox bootstrap + delete 409.**

In `python-service/routes.py`, AFTER the existing `import` block, add:
```python
import context_state
import quick_inbox
```

In the `startup()` handler, after `await db.init_db()`, add:
```python
    # Quick Inbox singleton — must exist before the first capture so voice
    # routing always has a fallback id.
    await quick_inbox.ensure_quick_inbox()
```

Replace the existing `delete_note` route to surface a 409:
```python
@app.delete("/notes/{note_id}")
async def delete_note(note_id: str):
    success = await db.delete_note(note_id)
    if not success:
        # Could be "not found" OR "protected (Quick Inbox)". Disambiguate.
        inbox = await db.get_quick_inbox()
        if inbox and inbox["id"] == note_id:
            raise HTTPException(
                status_code=409,
                detail="Quick Inbox cannot be deleted",
            )
        # else: nothing was deleted because the id doesn't exist.
    return {"success": success}
```

Add `/context` and `/quick-inbox` route handlers, right after the existing `/target` block:
```python
@app.get("/context")
async def get_context_route():
    """Return the current Electron context (foreground + open-note id)."""
    return context_state.get_context()


@app.post("/context")
async def set_context_route(body: dict):
    """Electron pushes here on every focus / open-note change.

    Body: {"foreground": bool, "open_note_id": str | null}
    """
    context_state.set_context(
        foreground=bool(body.get("foreground", False)),
        open_note_id=body.get("open_note_id"),
    )
    return context_state.get_context()


@app.get("/quick-inbox")
async def get_quick_inbox_route():
    """Return the Quick Inbox note row (id, title, etc.). Useful for the
    picker (sticky top entry) and the renderer's sidebar pinning."""
    inbox = await quick_inbox.ensure_quick_inbox()
    return inbox
```

- [ ] **Step 2: Manual verification via uvicorn.**

In a separate terminal, from the worktree root:
```bash
python-service/venv/Scripts/python.exe -m uvicorn python-service.routes:app --host 127.0.0.1 --port 8766 &
sleep 2
curl -s http://127.0.0.1:8766/quick-inbox
curl -s -X POST -H "Content-Type: application/json" -d '{"foreground":true,"open_note_id":"abc"}' http://127.0.0.1:8766/context
curl -s http://127.0.0.1:8766/context
```
Expected: Quick Inbox JSON with `is_quick_inbox: 1`; context POST echoes back the same payload; context GET shows `{"foreground": true, "open_note_id": "abc"}`. Kill the bg process when done: `kill %1`.

- [ ] **Step 3: Commit.**

```bash
git add python-service/routes.py
git commit -m "feat(voice): /context + /quick-inbox routes + delete-guard 409"
```

---

### Task 14: `note_generator.process_note` accepts a `routing_decision`

**Files:**
- Modify: `python-service/note_generator.py`
- Modify: `python-service/main.py` (call the router + pass decision)

**Key contract change:** `process_note` previously decided destination from `target_state`. Now it accepts a `routing_decision` (already resolved by `voice_routing.route` upstream) and uses that. `target_state` is kept as the fallback for the no-qualifier case where `context_state` says no foreground note (preserves existing picker-pinned behavior).

- [ ] **Step 1: Extend `process_note` signature and routing.**

In `python-service/note_generator.py`, change `process_note`'s signature + routing block (around lines 23-25 and 198-247):
```python
async def process_note(system_audio, command_audio, broadcast_fn,
                       media_was_paused=False, target=None,
                       language=None, routing_decision=None,
                       quick_inbox_id=None):
```

Replace the existing destination block (the `# Routing — user-selected target` section through the `target_state.clear_target()` branch) with:
```python
        # Routing precedence:
        # 1. voice_routing.RoutingDecision (set when a command transcript was
        #    available) wins outright.
        # 2. target_state pinned note (legacy picker pin) — keeps old behavior
        #    for users who haven't switched to voice routing.
        # 3. context_state foreground-open-note default for plain "Hey Deen, X".
        # 4. Quick Inbox.
        #
        # process_note never decides between these tiers itself; main.py is
        # responsible for handing in a routing_decision that already reflects
        # the right tier. We only fall back to (2/3/4) when routing_decision
        # is None (a code path we keep for the keyboard /trigger endpoint).
        import context_state
        import quick_inbox

        existing_note = None
        target_was_stale = False
        proposed_title = None
        create_new = False
        body_content = note_data.get("content", system_transcript)

        if routing_decision is not None:
            # Voice routing decided. Override body if the decision carried
            # routing-only content (e.g. it's possible the body is just the
            # in-qualifier tail; but for now we preserve the LLM-generated
            # `content` as the body).
            if routing_decision.kind == "existing":
                existing_note = await get_note(routing_decision.note_id) if routing_decision.note_id else None
                if existing_note is None:
                    target_was_stale = True
            elif routing_decision.kind == "create_new":
                create_new = True
                proposed_title = routing_decision.proposed_title
        else:
            # Legacy paths (no voice routing decision provided)
            if target and target.get("note_id"):
                existing_note = await get_note(target["note_id"])
                if existing_note is None:
                    target_was_stale = True
            elif target and target.get("create_new_pending"):
                create_new = True
            else:
                ctx = context_state.get_context()
                if ctx.get("foreground") and ctx.get("open_note_id"):
                    existing_note = await get_note(ctx["open_note_id"])
                if existing_note is None:
                    # Final fallback: Quick Inbox.
                    inbox = await quick_inbox.ensure_quick_inbox()
                    existing_note = inbox

        if existing_note:
            updated = await append_to_note(
                existing_note["id"], body_content
            )
            await broadcast_fn({"type": "note_updated", "note": updated})
            debug.log("Deen", "appended to existing note", existing_note["title"])
            # Stamp last_capture for the "continue" voice pattern.
            context_state.set_last_capture(existing_note["id"])
            # Spoken hear-back.
            import tts_client
            tts_client.say(f"Saved to {existing_note['title']}")
        else:
            title_to_use = proposed_title or note_data.get("title", "Untitled Note")
            note = await create_note(
                title=title_to_use,
                content=body_content,
                tags=note_data.get("tags", []),
                source=note_data.get("source", ""),
            )
            await broadcast_fn({"type": "note", "note": note})
            debug.log("Deen", "note created", note["title"])
            context_state.set_last_capture(note["id"])
            import tts_client
            tts_client.say(f"Saved to {note['title']}")

            if (target and target.get("create_new_pending")) or create_new:
                target_state.set_target(note["id"])
                await broadcast_fn({
                    "type": "target",
                    "note_id": note["id"],
                    "create_new_pending": False,
                    "title": note["title"],
                })
            elif target_was_stale:
                target_state.clear_target()
                await broadcast_fn({
                    "type": "target",
                    "note_id": None,
                    "create_new_pending": False,
                    "title": None,
                })
```

- [ ] **Step 2: Update `main.py` to call the router and pass `routing_decision`.**

In `python-service/main.py`, modify `on_wake_word_detected` — after `command_audio = record_command()` and before the `process_note` dispatch, transcribe the command (we need the text to parse) and run routing:

```python
        # Voice routing — parse the command transcript and decide destination
        # BEFORE the heavy system-audio pipeline runs. This lets us emit the
        # hear-back / disambiguation prompts early enough that the user isn't
        # left waiting in silence.
        command_text = ""
        if command_audio is not None and len(command_audio) > 0:
            try:
                from resampler import audio_to_wav_bytes
                import ai_client
                cmd_wav = audio_to_wav_bytes(command_audio)
                command_text = ai_client.transcribe_audio(cmd_wav, False) or ""
            except (OSError, RuntimeError, ValueError) as e:
                debug.warn("Main", "command pre-transcribe failed", e)

        routing_decision = None
        quick_inbox_id = None
        if _server_loop:
            # Fetch notes + ensure Quick Inbox on the server loop, then route.
            async def _decide():
                import database as db
                import quick_inbox as qi
                import voice_routing
                import context_state
                inbox = await qi.ensure_quick_inbox()
                notes = await db.get_all_notes()
                parsed = voice_routing.parse_command(command_text)
                # Foreground-open-note override for the no-qualifier case:
                # if user said no qualifier AND main window is foregrounded
                # with a note open, route there instead of Quick Inbox.
                if parsed.kind == "inbox":
                    ctx = context_state.get_context()
                    if ctx.get("foreground") and ctx.get("open_note_id"):
                        return inbox["id"], voice_routing.RoutingDecision(
                            kind="existing",
                            note_id=ctx["open_note_id"],
                            content=parsed.content,
                            confidence="high",
                        )
                decision = voice_routing.route(
                    parsed=parsed,
                    notes=notes,
                    quick_inbox_id=inbox["id"],
                    last_capture=context_state.get_last_capture(),
                )
                return inbox["id"], decision

            fut = asyncio.run_coroutine_threadsafe(_decide(), _server_loop)
            try:
                quick_inbox_id, routing_decision = fut.result(timeout=8)
            except (TimeoutError, Exception) as e:
                debug.warn("Main", "routing decide failed", e)
                routing_decision = None

            # Run disambiguation if the decision needs follow-up.
            if (routing_decision is not None
                    and routing_decision.kind == "needs_voice_followup"):
                routing_decision = run_disambiguation_loop(
                    routing_decision, quick_inbox_id
                )
```

Then update the `asyncio.run_coroutine_threadsafe(process_note(...))` call to pass through:
```python
            asyncio.run_coroutine_threadsafe(
                process_note(system_audio, command_audio, broadcast,
                             media_was_paused=media_was_paused,
                             target=frozen_target,
                             language=frozen_language,
                             routing_decision=routing_decision,
                             quick_inbox_id=quick_inbox_id),
                _server_loop,
            )
```

- [ ] **Step 3: Smoke-test imports.**

```bash
python-service/venv/Scripts/python.exe -c "import main; print('ok')"
```
Expected: "ok". Fix any circular import by moving more imports into function bodies.

- [ ] **Step 4: Manual end-to-end via /trigger (no wake-word needed).**

This isn't easy to test automatically — it requires real mic input. Defer to Task 20 (verification).

- [ ] **Step 5: Commit.**

```bash
git add python-service/main.py python-service/note_generator.py
git commit -m "feat(voice): wire RoutingDecision through main → process_note"
```

---

### Task 15: Spoken hear-back (already wired in Task 14)

Hear-back was baked into Task 14's `process_note` rewrite. **No separate task** — verify in Task 20's end-to-end run that `tts_client.say` is reached on every capture path.

This task header is kept as a checkbox for the executor to confirm.

- [ ] **Step 1: Grep that every save path calls `tts_client.say`.**

```bash
grep -n "tts_client.say" python-service/note_generator.py
```
Expected: 2 hits — one in the append-to-existing branch, one in the create-new branch.

- [ ] **Step 2: Commit (no-op task; already committed in Task 14).**

Skip — nothing to commit.

---

## Phase E — Bubble + UI

### Task 16: Electron context tracking — push `/context` from renderer

**Files:**
- Modify: `electron/main.js` (new IPC handler + window focus tracking + POST /context)
- Modify: `electron/preload.js` (expose `notifyOpenNote`)

- [ ] **Step 1: Add `notifyOpenNote` to `electron/preload.js`.**

In `electron/preload.js`, inside the existing `contextBridge.exposeInMainWorld('electronAPI', { ... })` block, add:
```javascript
  notifyOpenNote: (noteId) => ipcRenderer.invoke('context:open-note', noteId),
```

- [ ] **Step 2: Wire focus + open-note tracking in `electron/main.js`.**

In `electron/main.js`, near the `pythonRequest` helper, add:
```javascript
// ── Context tracker: pushes foreground + open-note id to Python so voice
//    routing can use them as the no-qualifier default. Best-effort — a
//    failed POST shouldn't break the UI. ────────────────────────────────
let _currentOpenNoteId = null;

async function pushContextToPython() {
  const foreground = !!(mainWindow && mainWindow.isFocused() && mainWindow.isVisible());
  try {
    await pythonRequest('POST', '/context', {
      foreground,
      open_note_id: foreground ? _currentOpenNoteId : null,
    });
  } catch (err) {
    // Silent — context is best-effort; voice routing falls back gracefully.
  }
}
```

In `createWindow()`, after the `mainWindow = new BrowserWindow(...)` block, add:
```javascript
  mainWindow.on('focus',  pushContextToPython);
  mainWindow.on('blur',   pushContextToPython);
  mainWindow.on('show',   pushContextToPython);
  mainWindow.on('hide',   pushContextToPython);
```

Near the existing `ipcMain.handle('trigger-note', ...)` block, add:
```javascript
ipcMain.handle('context:open-note', (_e, noteId) => {
  _currentOpenNoteId = noteId || null;
  return pushContextToPython();
});
```

Push once on startup once the python service comes up. After the existing `restoreLanguageToPython();` call in `app.whenReady`, add:
```javascript
  // Initial context push so Python has a foreground=true reading from boot,
  // not "false until the user clicks somewhere." Retries internally.
  setTimeout(pushContextToPython, 1500);
```

- [ ] **Step 3: Wire `App.jsx` to broadcast open-note changes.**

In `src/App.jsx`, after the existing `useEffect` hooks (around line 224), add:
```javascript
  // Push the open-note id to electron whenever the active view changes so
  // Python's context_state has the right value for "no-qualifier" routing
  // (Hey Deen with main window foregrounded + a note open → route there).
  useEffect(() => {
    const api = window.electronAPI;
    if (!api?.notifyOpenNote) return;
    const id = view === 'note' ? activeNoteId : null;
    api.notifyOpenNote(id).catch(() => {});
  }, [view, activeNoteId]);
```

- [ ] **Step 4: Smoke-test (manual).**

```bash
cd .claude/worktrees/canvas-5-voice-routing
npm run electron:dev
```
In a separate terminal:
```bash
curl -s http://127.0.0.1:8765/context
```
Expected after Electron is up: `{"foreground": true, "open_note_id": null}` (or the open note id if you've clicked into one). Toggle focus to another app → `{"foreground": false, ...}`.

Kill the dev server when satisfied.

- [ ] **Step 5: Commit.**

```bash
git add electron/main.js electron/preload.js src/App.jsx
git commit -m "feat(voice): electron pushes foreground+open-note to /context"
```

---

### Task 17: Bubble click context-aware default

**Files:**
- Modify: `electron/main.js` (`ipcMain.handle('bubble:trigger-note', ...)`)

**Behavior change:** today the bubble click ALWAYS opens the picker. After this task: if main window is foreground AND a note is open, the click TRIGGERS A CAPTURE (skipping the picker). Otherwise it opens the (new) pinboard picker.

- [ ] **Step 1: Modify the bubble-click handler.**

In `electron/main.js`, find the existing `ipcMain.handle('bubble:trigger-note', () => triggerNoteCapture());` and the bubble.html click handler (`window.bubbleAPI?.openPicker()`). The bubble currently calls `openPicker` on click; we need to route it through main process logic that checks context first.

Replace the existing `ipcMain.handle('picker:open', () => { showPicker(); });` with:
```javascript
ipcMain.handle('picker:open', () => {
  // Context-aware default: if main window is foregrounded AND a note is open,
  // a bubble click triggers an immediate capture for that note instead of
  // popping the picker. Matches the spec: "Picker is for desk mode only."
  const foreground = !!(mainWindow && mainWindow.isFocused() && mainWindow.isVisible());
  if (foreground && _currentOpenNoteId) {
    debug.log('Bubble', 'context-aware capture to open note', _currentOpenNoteId);
    triggerNoteCapture();
    return;
  }
  showPicker();
});
```

- [ ] **Step 2: Manual verification.**

Start `npm run electron:dev`. With main window focused + a note open, click the bubble. Expected: the listening UI appears (capture triggered) without the picker opening. Click the bubble with the main window blurred (e.g. focus another app first). Expected: picker opens.

- [ ] **Step 3: Commit.**

```bash
git add electron/main.js
git commit -m "feat(voice): bubble click is context-aware (capture vs picker)"
```

---

### Task 18: Pinboard-snapshot picker

**Files:**
- Modify: `electron/picker.html` (full body+script rewrite)
- Modify: `electron/picker-preload.js` (add `getPickerSnapshot`)
- Modify: `electron/main.js` (new `picker:snapshot` IPC handler)

**Design:** the picker becomes a CSS-grid of small "mini cards" — title, preview (first 60 chars of content), last-updated. Quick Inbox is a sticky FIRST card with a 📥 icon. Click any card → set target → close. The current tree-view styling stays as a fallback for when the grid is empty.

CSS classes prefixed with `.picker-` (the bubble itself already uses unprefixed styles; we won't rename those in this task, but new picker classes use the prefix to avoid future collisions).

- [ ] **Step 1: Add `picker:snapshot` handler in `electron/main.js`.**

In `electron/main.js`, after the existing `picker:tree` handler, add:
```javascript
ipcMain.handle('picker:snapshot', async () => {
  // Snapshot of notes for the pinboard picker. We include the Quick Inbox
  // separately so the renderer can pin it at the top regardless of sort order.
  try {
    const [notes, inbox] = await Promise.all([
      pythonRequest('GET', '/notes', null),
      pythonRequest('GET', '/quick-inbox', null),
    ]);
    // Filter Quick Inbox out of the main grid (it'll render as the sticky top card).
    const inboxId = inbox?.id;
    const regular = (notes || []).filter((n) => n.id !== inboxId);
    return { inbox: inbox || null, notes: regular };
  } catch (err) {
    debug.error('Picker', 'snapshot failed', err.message);
    return { inbox: null, notes: [] };
  }
});
```

- [ ] **Step 2: Expose `getPickerSnapshot` in `electron/picker-preload.js`.**

In `electron/picker-preload.js`, inside the existing `contextBridge.exposeInMainWorld('pickerAPI', { ... })` block, add:
```javascript
  getPickerSnapshot: () => ipcRenderer.invoke('picker:snapshot'),
```

- [ ] **Step 3: Rewrite `electron/picker.html` body + script for the pinboard grid.**

Replace `electron/picker.html` ENTIRELY with:
```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }

  html, body {
    width: 360px;
    height: 480px;
    overflow: hidden;
    background: transparent;
    user-select: none;
    -webkit-font-smoothing: antialiased;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    color: #fff;
  }

  .picker-panel {
    width: 100%;
    height: 100%;
    background: rgba(20, 20, 24, 0.94);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 14px;
    display: flex;
    flex-direction: column;
    box-shadow:
      0 24px 60px rgba(0, 0, 0, 0.55),
      0 2px 6px rgba(0, 0, 0, 0.35),
      inset 0 1px 0 rgba(255, 255, 255, 0.06);
  }

  .picker-header {
    padding: 12px 16px 8px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: rgba(255, 255, 255, 0.55);
    flex-shrink: 0;
  }

  .picker-inbox-row {
    margin: 0 10px 8px;
    padding: 12px 14px;
    border-radius: 10px;
    background: linear-gradient(135deg, rgba(120, 210, 255, 0.18), rgba(120, 210, 255, 0.04));
    border: 1px solid rgba(120, 210, 255, 0.28);
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 10px;
    transition: background 0.12s ease, transform 0.08s ease;
    flex-shrink: 0;
  }
  .picker-inbox-row:hover {
    background: linear-gradient(135deg, rgba(120, 210, 255, 0.24), rgba(120, 210, 255, 0.08));
  }
  .picker-inbox-row:active { transform: scale(0.985); }
  .picker-inbox-row .picker-inbox-icon { font-size: 18px; }
  .picker-inbox-row .picker-inbox-text {
    font-size: 13px;
    font-weight: 500;
    color: rgba(255, 255, 255, 0.95);
  }
  .picker-inbox-row .picker-inbox-hint {
    font-size: 11px;
    color: rgba(255, 255, 255, 0.55);
    margin-left: auto;
  }

  .picker-grid-scroll {
    flex: 1;
    overflow-y: auto;
    padding: 4px 10px 10px;
  }
  .picker-grid-scroll::-webkit-scrollbar { width: 6px; }
  .picker-grid-scroll::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.12);
    border-radius: 3px;
  }

  .picker-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }

  .picker-card {
    padding: 10px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
    cursor: pointer;
    height: 88px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    transition: background 0.12s ease, border-color 0.12s ease;
  }
  .picker-card:hover {
    background: rgba(255, 255, 255, 0.09);
    border-color: rgba(255, 255, 255, 0.18);
  }
  .picker-card.active {
    border-color: rgba(255, 255, 255, 0.35);
    background: rgba(255, 255, 255, 0.12);
  }
  .picker-card-title {
    font-size: 12px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.95);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-bottom: 4px;
  }
  .picker-card-preview {
    font-size: 10px;
    color: rgba(255, 255, 255, 0.55);
    line-height: 1.3;
    flex: 1;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
  }
  .picker-card-time {
    font-size: 9px;
    color: rgba(255, 255, 255, 0.35);
    margin-top: 4px;
  }

  .picker-new-row {
    margin: 8px 10px 10px;
    padding: 10px 12px;
    border-radius: 10px;
    background: linear-gradient(135deg, rgba(255,255,255,0.10), rgba(255,255,255,0.04));
    border: 1px solid rgba(255, 255, 255, 0.14);
    color: #fff;
    font-size: 12px;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
    flex-shrink: 0;
  }
  .picker-new-row:hover { background: linear-gradient(135deg, rgba(255,255,255,0.16), rgba(255,255,255,0.07)); }
  .picker-new-row .picker-plus {
    width: 18px; height: 18px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.15);
    display: flex; align-items: center; justify-content: center;
    font-size: 14px;
  }

  .picker-empty {
    padding: 32px 16px;
    text-align: center;
    color: rgba(255, 255, 255, 0.45);
    font-size: 12px;
    font-style: italic;
  }
</style>
</head>
<body>
  <div class="picker-panel">
    <div class="picker-header">Save notes to</div>

    <div class="picker-inbox-row" id="inbox-row">
      <span class="picker-inbox-icon">📥</span>
      <span class="picker-inbox-text">Quick Inbox</span>
      <span class="picker-inbox-hint">always there</span>
    </div>

    <div class="picker-grid-scroll">
      <div class="picker-grid" id="grid">
        <div class="picker-empty">Loading…</div>
      </div>
    </div>

    <div class="picker-new-row" id="new-empty">
      <span class="picker-plus">+</span>
      <span>Create empty note</span>
    </div>
  </div>

<script>
  const gridEl = document.getElementById('grid');
  const inboxRow = document.getElementById('inbox-row');
  const newEmptyRow = document.getElementById('new-empty');

  function relTime(iso) {
    if (!iso) return '';
    const sec = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
    if (sec < 60) return 'just now';
    const min = Math.round(sec / 60);
    if (min < 60) return min + 'm ago';
    const hr = Math.round(min / 60);
    if (hr < 24) return hr + 'h ago';
    const day = Math.round(hr / 24);
    if (day < 7) return day + 'd ago';
    return new Date(iso).toLocaleDateString();
  }

  function previewText(content) {
    if (!content) return '';
    // Strip markdown noise for a glance-able preview.
    const stripped = String(content)
      .replace(/[#*_>`~\[\]()]/g, '')
      .replace(/\s+/g, ' ')
      .trim();
    return stripped.slice(0, 100);
  }

  function renderCards(snapshot, activeId) {
    const notes = snapshot?.notes || [];
    if (notes.length === 0) {
      gridEl.innerHTML = '<div class="picker-empty">No notes yet</div>';
      return;
    }
    gridEl.innerHTML = '';
    // Sort notes by updated_at descending (recent first), so the picker
    // surfaces what the user is most likely to want.
    const sorted = [...notes].sort((a, b) =>
      (b.updated_at || '').localeCompare(a.updated_at || '')
    );
    for (const n of sorted) {
      const card = document.createElement('div');
      card.className = 'picker-card' + (n.id === activeId ? ' active' : '');
      card.innerHTML =
        '<div class="picker-card-title"></div>' +
        '<div class="picker-card-preview"></div>' +
        '<div class="picker-card-time"></div>';
      card.querySelector('.picker-card-title').textContent = n.title || 'Untitled';
      card.querySelector('.picker-card-preview').textContent = previewText(n.content);
      card.querySelector('.picker-card-time').textContent = relTime(n.updated_at);
      card.addEventListener('click', () => window.pickerAPI.select(n.id));
      gridEl.appendChild(card);
    }
  }

  async function load() {
    const [snapshot, target] = await Promise.all([
      window.pickerAPI.getPickerSnapshot(),
      window.pickerAPI.getTarget(),
    ]);
    renderCards(snapshot, target?.note_id);
  }

  inboxRow.addEventListener('click', async () => {
    // Route to Quick Inbox = pin target there.
    const snapshot = await window.pickerAPI.getPickerSnapshot();
    if (snapshot?.inbox?.id) {
      window.pickerAPI.select(snapshot.inbox.id);
    }
  });

  newEmptyRow.addEventListener('click', () => {
    window.pickerAPI.createEmptyNote();
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') window.pickerAPI.close();
  });

  window.addEventListener('focus', load);
  load();
</script>
</body>
</html>
```

- [ ] **Step 4: Resize the picker window to fit the new layout.**

In `electron/main.js`, update the constants:
```javascript
const PICKER_WIDTH = 360;
const PICKER_HEIGHT = 480;
```
(The existing values were 300×480; new is 360 wide to fit the 2-column grid.)

- [ ] **Step 5: Manual verification.**

Start `npm run electron:dev`. Click the bubble while main window is blurred. Expected: pinboard grid with Quick Inbox sticky on top, 2-column cards below. Clicking a card pins target + closes picker.

- [ ] **Step 6: Commit.**

```bash
git add electron/picker.html electron/picker-preload.js electron/main.js
git commit -m "feat(voice): pinboard-snapshot picker with Quick Inbox sticky"
```

---

### Task 19: `App.jsx` + `Sidebar.jsx` Quick Inbox handling

**Files:**
- Modify: `src/App.jsx` (refuse delete on Quick Inbox)
- Modify: `src/components/Sidebar.jsx` (render Quick Inbox at top, hide from archive)

- [ ] **Step 1: Add Quick Inbox special-case to `App.jsx`.**

In `src/App.jsx`, modify `deletePermanently` to refuse the Quick Inbox:
```javascript
  const deletePermanently = useCallback(async (id) => {
    const target = notes.find((n) => n.id === id);
    if (target?.is_quick_inbox) {
      // Quick Inbox is protected. Don't even attempt the DELETE — Python
      // would return 409, which we'd just have to render an error toast for.
      debug.log('App', 'refusing delete of Quick Inbox');
      return;
    }
    const success = await deleteNote(id);
    if (success) {
      overlay.forgetNote(id);
      if (activeNoteId === id) {
        setView('home');
        setActiveNoteId(null);
      }
    }
  }, [deleteNote, overlay, activeNoteId, notes]);
```

- [ ] **Step 2: Modify `Sidebar.jsx` to surface Quick Inbox at top.**

Read `src/components/Sidebar.jsx` first (paths and props vary by current state — locate the filter section + notes list). Add a Quick Inbox row above the filter chips:

```jsx
// Inside Sidebar's render, locate the existing sidebar content (filter chips
// + groups list) and prepend:
{filter.type !== 'archive' && (() => {
  const inbox = notes.find((n) => n.is_quick_inbox);
  if (!inbox) return null;
  const isActive = filter.type === 'all' && /* approximate "showing inbox"; if your
    filter shape uses note-id selection, swap this for an explicit check. */ false;
  return (
    <div
      className="sidebar-quick-inbox-row"
      onClick={() => {
        // Reuse the "open this note" path. Sidebar usually surfaces filters,
        // not note-opens — wire up via the existing onFilterChange shape if
        // your Home view supports a single-note filter. Otherwise just emit
        // a setActiveNoteId via a new prop. (See App.jsx for the lift-up.)
        if (typeof onOpenNote === 'function') onOpenNote(inbox.id);
      }}
    >
      <span className="sidebar-quick-inbox-icon">📥</span>
      <span className="sidebar-quick-inbox-label">Quick Inbox</span>
    </div>
  );
})()}
```

Add a tiny CSS rule (in whichever Sidebar.module.css or global.css the sidebar uses — search for `.sidebar-` to find the convention):
```css
.sidebar-quick-inbox-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  margin: 4px 8px 8px;
  border-radius: 8px;
  cursor: pointer;
  background: linear-gradient(135deg, rgba(120, 210, 255, 0.12), rgba(120, 210, 255, 0.04));
  border: 1px solid rgba(120, 210, 255, 0.20);
  font-size: 13px;
  color: rgba(255, 255, 255, 0.92);
  transition: background 0.12s ease;
}
.sidebar-quick-inbox-row:hover {
  background: linear-gradient(135deg, rgba(120, 210, 255, 0.18), rgba(120, 210, 255, 0.06));
}
```

If `Sidebar` doesn't already receive `onOpenNote`, lift it from App.jsx by passing `handleOpenNote` as a new prop.

- [ ] **Step 3: Manual verification.**

Start `npm run electron:dev`. Expected: Quick Inbox row at top of sidebar with 📥 icon. Switch to Archive view — Quick Inbox row disappears. Try to delete it from Home: nothing happens (debug log shows "refusing").

- [ ] **Step 4: Commit.**

```bash
git add src/App.jsx src/components/Sidebar.jsx src/**/*.css
git commit -m "feat(voice): Quick Inbox sidebar pin + delete refusal"
```

---

## Phase F — Ship

### Task 20: End-to-end verification (4 patterns + bubble UX)

**Files:** none modified (verification only).

**Production-code escalation rule:** if any of the 4 patterns fails AND the fix requires code changes OUTSIDE this sub-project's planned scope (e.g. fixing the wake-word detection, or fixing AssemblyAI transcription), STOP and report `DONE_WITH_CONCERNS` with the specific failure and proposed fix. Do not silently broaden scope.

- [ ] **Step 1: Run the full automated test suite.**

```bash
cd .claude/worktrees/canvas-5-voice-routing
python-service/venv/Scripts/python.exe -m pytest python-service/tests/ -v
npm test
```
Expected: all tests pass. Number to confirm: ~50 Python tests, ~existing N JS tests.

- [ ] **Step 2: Pattern 1 — `"Hey Deen, [content]"` → Quick Inbox.**

Start `npm run electron:dev`. Make sure main window is BLURRED (focus another app). Say: "Hey Deen, lorem ipsum dolor sit amet."

Expected:
- Bubble enters "command" → "noting" phase
- New row appears in Quick Inbox (open it from sidebar to verify)
- Audible "Saved to Quick Inbox" (if Sub-project 4 has shipped; otherwise silent)

- [ ] **Step 3: Pattern 2 — `"Hey Deen, in <name>, [content]"`.**

Create a test note titled "Sapiens" via the picker first. Then say: "Hey Deen, in Sapiens, the author argues humans love stories."

Expected:
- Content appended to "Sapiens" note (not Quick Inbox)
- Audible "Saved to Sapiens"

Edge case: rename the note to "Sapians" (typo). Repeat the test. Routing should still pick it via fuzzy match.

- [ ] **Step 4: Pattern 3 — `"Hey Deen, new note about <topic>, [content]"`.**

Say: "Hey Deen, new note about cooking eggs, scramble at medium-low heat."

Expected:
- New note created titled "Cooking Eggs"
- Content "scramble at medium-low heat" inside it
- Audible "Saved to Cooking Eggs"

- [ ] **Step 5: Pattern 4 — `"Hey Deen, continue, [content]"`.**

Right after Pattern 3, say: "Hey Deen, continue, beat the eggs first."

Expected:
- Content appended to "Cooking Eggs" (the most-recent capture)
- Audible "Saved to Cooking Eggs"

Now wait 31 minutes (or fake the clock by editing `context_state._last_capture['timestamp']` via Python REPL). Repeat. Expected: disambiguation loop fires asking "Nothing to continue — name a note, or say inbox."

- [ ] **Step 6: Disambiguation flow.**

Create two notes: "Sapiens chapter 1" and "Sapiens chapter 2". Say: "Hey Deen, in Sapiens, the author argues..."

Expected: app speaks back "Sapiens chapter 1 or Sapiens chapter 2? Say which." → record yourself saying "chapter 2" → content lands in "Sapiens chapter 2".

- [ ] **Step 7: Bubble UX — context-aware default.**

With main window foregrounded + "Cooking Eggs" open, click the bubble (not voice). Expected: capture triggers immediately (listening UI shows). No picker.

Blur main window. Click bubble. Expected: pinboard picker opens.

- [ ] **Step 8: Quick Inbox protection.**

Open the sidebar. Hover Quick Inbox — no delete button (or visible disabled). If a delete is forced via DevTools, expect a no-op + log.

- [ ] **Step 9: Document any deviations.**

If steps 2–8 reveal a behavior mismatch with the spec, write findings to `docs/superpowers/specs/2026-05-24-canvas-redesign-design.md` as a "v1 caveats" addendum AND open a TODO in this plan for v1.1 follow-up. Do NOT silently fix production code outside the planned tasks.

---

### Task 21: PR + post URL

**Files:** none modified.

- [ ] **Step 1: Push branch + open PR.**

```bash
cd .claude/worktrees/canvas-5-voice-routing
git push -u origin canvas/5-voice-routing
gh pr create \
  --base main \
  --title "feat(voice): 4-pattern routing + quick inbox + bubble redesign" \
  --body "$(cat <<'EOF'
## Summary
- 4-pattern Hey Deen voice grammar (inbox / in <name> / new note about <topic> / continue) with tiered routing (rapidfuzz + optional embedding → Haiku 4.5 fallback → voice disambiguation loop)
- Quick Inbox singleton with delete-guard + sidebar pin + sticky-top picker entry
- Bubble redesign: context-aware default (foreground+note-open → silent capture) + pinboard-snapshot picker for desk mode
- Spoken hear-back via /tts/say (graceful no-op until Sub-project 4 ships the endpoint)

## Test plan
- [x] pytest python-service/tests/ — all unit tests for parser, matcher, routing, response parsing, Haiku client, Quick Inbox, context_state, tts_client pass
- [x] npm test — existing electron tests still pass
- [x] Manual end-to-end of all 4 voice patterns (see plan Task 20)
- [x] Bubble context-aware default verified (focused+note-open → capture, else picker)
- [x] Quick Inbox cannot be deleted (DELETE /notes/<inbox-id> returns 409)

## Out of scope (deferred to other sub-projects)
- Structure-aware in-canvas placement (Sub-project 6)
- Canvas UI itself (Sub-projects 1 + 6)
- Dictation modifier hotkeys (Sub-project 4)
- Auto-cleanup AI suggestions for Quick Inbox

Plan: docs/superpowers/plans/2026-05-24-voice-routing-v1.md
Spec: docs/superpowers/specs/2026-05-24-canvas-redesign-design.md (Voice capture section)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 2: Capture + share PR URL.**

`gh pr create` prints the URL on success. Copy it. Post it back to Abed.

---

## Appendix — Self-review checklist (run after writing this plan)

Run through this as the plan author before handing off:

- **Spec coverage** — every bullet in the spec's Voice capture section maps to at least one task:
  - 4 voice grammar patterns → Task 5 (parser), Tasks 7+9 (routing)
  - Tiered routing (local → Haiku) → Tasks 6, 7, 8, 9
  - Voice-only disambiguation → Tasks 11, 12
  - Quick Inbox singleton → Tasks 2, 3
  - Bubble context-aware default → Task 17
  - Pinboard picker for desk mode → Task 18
  - Spoken hear-back via /tts/say → Tasks 10, 14
  - Quick Inbox sticky in picker → Task 18
  - Quick Inbox in sidebar → Task 19
  - Quick Inbox un-deletable → Tasks 2, 13, 19

- **Placeholder scan** — searched plan for "TBD", "TODO" in step content, "implement later", "similar to" — none found. Code blocks present at every Step-3 implementation step.

- **Type consistency** — `RoutingDecision`, `ParsedCommand`, `MatchResult`, `parse_command()`, `route_local()`, `route()`, `parse_response()`, `ensure_quick_inbox()`, `is_quick_inbox_id()`, `set_context()`, `get_last_capture()` referenced consistently across tasks.

- **Production-code escalation** — every test-only task explicitly states the rule. Implementer should not silently expand scope.

- **Backwards compatibility** — `target_state` and `create_new_pending` flow preserved as fallback paths in `process_note` (Task 14) so the existing picker still works.

- **Graceful degradation** — sentence-transformers, anthropic key, and `/tts/say` are all optional. Voice routing degrades correctly when any of them is missing.
