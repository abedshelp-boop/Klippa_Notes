import aiosqlite
import json
import uuid
from datetime import datetime, timezone
from config import DB_PATH


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

        # Migration for existing databases that lack the video_url column.
        cursor = await db.execute("PRAGMA table_info(notes)")
        columns = {row[1] for row in await cursor.fetchall()}
        if "video_url" not in columns:
            await db.execute("ALTER TABLE notes ADD COLUMN video_url TEXT DEFAULT ''")

        await db.commit()


async def create_note(title: str, content: str, tags: list,
                      source: str = "", video_url: str = "") -> dict:
    note_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    note = {
        "id": note_id,
        "title": title,
        "content": content,
        "tags": json.dumps(tags),
        "source": source,
        "video_url": video_url,
        "created_at": now,
        "updated_at": now,
    }
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO notes (id, title, content, tags, source, video_url, created_at, updated_at) "
            "VALUES (:id, :title, :content, :tags, :source, :video_url, :created_at, :updated_at)",
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
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        await db.commit()
        return cursor.rowcount > 0


async def search_notes(query: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM notes WHERE title LIKE ? OR content LIKE ? ORDER BY created_at DESC",
            (f"%{query}%", f"%{query}%"),
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]


async def find_note_by_video_url(video_url: str) -> dict | None:
    """Return the most recent note associated with a video URL, or None."""
    if not video_url:
        return None
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM notes WHERE video_url = ? ORDER BY created_at DESC LIMIT 1",
            (video_url,),
        )
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None


async def append_to_note(note_id: str, new_content: str) -> dict | None:
    """Append markdown content to an existing note and update its timestamp."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE notes SET content = content || ? , updated_at = ? WHERE id = ?",
            ("\n\n---\n\n" + new_content, now, note_id),
        )
        await db.commit()
    return await get_note(note_id)


def _row_to_dict(row) -> dict:
    d = dict(row)
    try:
        d["tags"] = json.loads(d.get("tags", "[]"))
    except (json.JSONDecodeError, TypeError):
        d["tags"] = []
    return d
