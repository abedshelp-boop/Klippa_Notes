import aiosqlite
import json
import uuid
from datetime import datetime, timezone
from config import DB_PATH

# Sentinel used by update_note() to distinguish "leave field alone" from "set to NULL".
_UNSET = object()


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                tags TEXT DEFAULT '[]',
                source TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                video_url TEXT DEFAULT ''
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                parent_id TEXT REFERENCES groups(id) ON DELETE SET NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Migration for existing databases that lack the video_url column.
        cursor = await db.execute("PRAGMA table_info(notes)")
        columns = {row[1] for row in await cursor.fetchall()}
        if "video_url" not in columns:
            await db.execute("ALTER TABLE notes ADD COLUMN video_url TEXT DEFAULT ''")

        # Migration for existing databases that lack the group_id column.
        # SQLite accepts REFERENCES in the column def but doesn't enforce it
        # unless PRAGMA foreign_keys = ON; we handle cascade manually in delete_group.
        if "group_id" not in columns:
            await db.execute(
                "ALTER TABLE notes ADD COLUMN group_id TEXT "
                "REFERENCES groups(id) ON DELETE SET NULL"
            )

        # Quick Inbox singleton flag — set on the one special inbox note so
        # we can find it via SELECT and protect it from deletion.
        if "is_quick_inbox" not in columns:
            await db.execute(
                "ALTER TABLE notes ADD COLUMN is_quick_inbox INTEGER DEFAULT 0"
            )

        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_groups_parent ON groups(parent_id)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_notes_group ON notes(group_id)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_notes_quick_inbox "
            "ON notes(is_quick_inbox) WHERE is_quick_inbox = 1"
        )

        await db.commit()


async def create_note(title: str, content: str, tags: list,
                      source: str = "", video_url: str = "",
                      group_id: str | None = None) -> dict:
    note_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    note = {
        "id": note_id,
        "title": title,
        "content": content,
        "tags": json.dumps(tags),
        "source": source,
        "video_url": video_url,
        "group_id": group_id,
        "created_at": now,
        "updated_at": now,
    }
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO notes (id, title, content, tags, source, video_url, group_id, created_at, updated_at) "
            "VALUES (:id, :title, :content, :tags, :source, :video_url, :group_id, :created_at, :updated_at)",
            note,
        )
        await db.commit()
    note["tags"] = tags
    return note


async def get_all_notes() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM notes ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]


async def get_note(note_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None


async def delete_note(note_id: str) -> bool:
    """Delete a note. Refuses to delete the Quick Inbox (returns False)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT is_quick_inbox FROM notes WHERE id = ?", (note_id,)
        )
        row = await cursor.fetchone()
        if row and (row["is_quick_inbox"] or 0):
            # Quick Inbox is protected — undeletable singleton.
            return False
        cursor = await db.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        await db.commit()
        return cursor.rowcount > 0


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
    is responsible for the get-then-create guard to avoid creating two."""
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


async def search_notes(query: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM notes WHERE title LIKE ? OR content LIKE ? ORDER BY created_at DESC",
            (f"%{query}%", f"%{query}%"),
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]


async def append_to_note(note_id: str, new_content: str,
                         separator: str = "\n\n---\n\n") -> dict | None:
    """Append markdown content to an existing note and update its timestamp.

    The default separator preserves the legacy behavior (horizontal rule
    between consecutive captures). Push-to-talk dictation passes "\\n\\n"
    for a softer break.
    """
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE notes SET content = content || ? , updated_at = ? WHERE id = ?",
            (separator + new_content, now, note_id),
        )
        await db.commit()
    return await get_note(note_id)


async def update_note(note_id: str, *,
                      title=_UNSET, content=_UNSET,
                      group_id=_UNSET, tags=_UNSET, source=_UNSET) -> dict | None:
    """Partial update of a note. Pass _UNSET (default) to leave a field alone.

    Pass None for `group_id` to detach a note from its group.
    `tags` may be a list (will be JSON-encoded) or a JSON string.
    Returns the updated note dict, or None if the id doesn't exist.
    """
    fields: list[str] = []
    values: list = []

    if title is not _UNSET:
        fields.append("title = ?")
        values.append(title)
    if content is not _UNSET:
        fields.append("content = ?")
        values.append(content)
    if group_id is not _UNSET:
        fields.append("group_id = ?")
        values.append(group_id)
    if tags is not _UNSET:
        fields.append("tags = ?")
        values.append(tags if isinstance(tags, str) else json.dumps(tags))
    if source is not _UNSET:
        fields.append("source = ?")
        values.append(source)

    if not fields:
        # Nothing to update — return current state.
        return await get_note(note_id)

    fields.append("updated_at = ?")
    values.append(datetime.now(timezone.utc).isoformat())
    values.append(note_id)

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            f"UPDATE notes SET {', '.join(fields)} WHERE id = ?",
            tuple(values),
        )
        await db.commit()
        if cursor.rowcount == 0:
            return None
    return await get_note(note_id)


# --------------------------- Groups -----------------------------------------


async def create_group(name: str, parent_id: str | None = None) -> dict:
    group_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    group = {
        "id": group_id,
        "name": name,
        "parent_id": parent_id,
        "created_at": now,
        "updated_at": now,
    }
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO groups (id, name, parent_id, created_at, updated_at) "
            "VALUES (:id, :name, :parent_id, :created_at, :updated_at)",
            group,
        )
        await db.commit()
    return group


async def get_all_groups() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM groups ORDER BY name COLLATE NOCASE"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_group(group_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM groups WHERE id = ?", (group_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_group(group_id: str, *,
                       name=_UNSET, parent_id=_UNSET) -> dict | None:
    """Partial update of a group (rename and/or reparent).

    Pass None for `parent_id` to make a group a top-level group.
    Self-parenting and circular references are NOT validated here — callers
    in routes.py should reject those before calling.
    """
    fields: list[str] = []
    values: list = []
    if name is not _UNSET:
        fields.append("name = ?")
        values.append(name)
    if parent_id is not _UNSET:
        fields.append("parent_id = ?")
        values.append(parent_id)

    if not fields:
        return await get_group(group_id)

    fields.append("updated_at = ?")
    values.append(datetime.now(timezone.utc).isoformat())
    values.append(group_id)

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            f"UPDATE groups SET {', '.join(fields)} WHERE id = ?",
            tuple(values),
        )
        await db.commit()
        if cursor.rowcount == 0:
            return None
    return await get_group(group_id)


async def delete_group(group_id: str) -> bool:
    """Delete a group, orphaning its notes (group_id=NULL) and subgroups
    (parent_id=NULL). Manual cascade since FKs aren't enforced.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # Detach notes that were in this group.
        await db.execute(
            "UPDATE notes SET group_id = NULL WHERE group_id = ?",
            (group_id,),
        )
        # Promote subgroups to top-level (orphan them to root).
        await db.execute(
            "UPDATE groups SET parent_id = NULL WHERE parent_id = ?",
            (group_id,),
        )
        cursor = await db.execute(
            "DELETE FROM groups WHERE id = ?", (group_id,)
        )
        await db.commit()
        return cursor.rowcount > 0


def _row_to_dict(row) -> dict:
    d = dict(row)
    try:
        d["tags"] = json.loads(d.get("tags", "[]"))
    except (json.JSONDecodeError, TypeError):
        # Legacy rows may store a Python repr or NULL in the tags column;
        # default to [] silently. Fires on every legacy row read — a log
        # here would be pure noise.
        d["tags"] = []
    # Default the Quick Inbox flag to 0 for legacy rows that pre-date the
    # column — SQLite returns NULL there, but the API contract is integer.
    d["is_quick_inbox"] = int(d.get("is_quick_inbox") or 0)
    return d
