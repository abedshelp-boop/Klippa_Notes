import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

import database as db
import video_context

app = FastAPI(title="Deen-Notes API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

connected_clients: list[WebSocket] = []

_trigger_callback = None


def set_trigger_callback(callback):
    global _trigger_callback
    _trigger_callback = callback


async def broadcast(message: dict):
    """Send a JSON message to all connected WebSocket clients."""
    data = json.dumps(message, default=str)
    disconnected = []
    for ws in connected_clients:
        try:
            await ws.send_text(data)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        connected_clients.remove(ws)


@app.on_event("startup")
async def startup():
    await db.init_db()


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_clients.append(ws)
    try:
        await ws.send_text(json.dumps({"type": "status", "status": "listening"}))
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if ws in connected_clients:
            connected_clients.remove(ws)


@app.get("/notes")
async def list_notes():
    return await db.get_all_notes()


@app.get("/notes/search")
async def search_notes(q: str = ""):
    if not q.strip():
        return await db.get_all_notes()
    return await db.search_notes(q)


@app.get("/notes/{note_id}")
async def get_note(note_id: str):
    note = await db.get_note(note_id)
    if note is None:
        return {"error": "Note not found"}, 404
    return note


@app.delete("/notes/{note_id}")
async def delete_note(note_id: str):
    success = await db.delete_note(note_id)
    return {"success": success}


@app.post("/trigger")
async def trigger_note():
    """Trigger note capture via keyboard shortcut or UI button."""
    if _trigger_callback:
        import threading
        threading.Thread(target=_trigger_callback, daemon=True).start()
        return {"success": True, "message": "Note capture triggered"}
    return {"success": False, "message": "Trigger callback not set"}


@app.post("/video-context")
async def update_video_context(body: dict):
    """Receive current video info from the Chrome extension."""
    title = body.get("title")
    url = body.get("url")
    if title and url:
        video_context.set_video(title, url)
    else:
        video_context.clear_video()
    return {"success": True}


@app.get("/video-context")
async def get_video_context():
    """Return the currently detected video (if any)."""
    return video_context.get_video() or {"title": None, "url": None}


@app.get("/settings")
async def get_settings():
    """Return current runtime settings. API keys are reported as booleans
    only — we never echo the actual key back to the UI."""
    import config
    return {
        "buffer_length": config.BUFFER_DURATION_SEC,
        "has_openai_key": bool(config.OPENAI_API_KEY),
        "has_assemblyai_key": bool(config.ASSEMBLYAI_API_KEY),
    }


@app.post("/settings")
async def update_settings(body: dict):
    """Update settings at runtime (stored in memory, not persisted to .env)."""
    import config
    import ai_client

    if body.get("openai_api_key"):
        config.OPENAI_API_KEY = body["openai_api_key"]
        ai_client._openai_client = None
    if body.get("assemblyai_api_key"):
        config.ASSEMBLYAI_API_KEY = body["assemblyai_api_key"]
        ai_client._aai_configured_key = None  # force reconfig on next call
    if body.get("buffer_length"):
        config.BUFFER_DURATION_SEC = int(body["buffer_length"])

    return {"success": True}
