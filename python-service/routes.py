import asyncio
import json
import os
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from openai import APIError as OpenAIAPIError

import ai_client
import database as db
import language as language_state
import tts_kokoro
import target as target_state
from debug import debug
from wake_word import get_wake_word_state

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
        except (ConnectionError, RuntimeError, WebSocketDisconnect):
            debug.warn("routes", "WS broadcast send failed — marking disconnected")
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
        # Send the *current* wake-word state on connect — late-joining clients
        # need this because the broadcast may have fired before they connected
        # (or before the asyncio loop was even up). Without it, a bubble
        # opened after wake-word died would silently show "alive".
        ww = get_wake_word_state()
        await ws.send_text(json.dumps({
            "type": "wake_word_state",
            "status": ww["status"],
            "error": ww["error"],
        }))
        # Late-joining clients also need the current language preference so
        # the language picker can render its active row without a separate
        # /language GET round-trip.
        await ws.send_text(json.dumps({
            "type": "language",
            **language_state.get_language(),
        }))
        await ws.send_text(json.dumps({"type": "status", "status": "listening"}))
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        # Normal client disconnect — cleanup happens in finally:
        pass
    finally:
        if ws in connected_clients:
            connected_clients.remove(ws)


@app.get("/health")
async def health():
    """Diagnostic endpoint: tells you whether each background subsystem is
    actually doing its job, vs. having silently failed at startup."""
    return {
        "python_pid": os.getpid(),
        "wake_word": get_wake_word_state(),
        "ws_clients": len(connected_clients),
    }


@app.get("/notes")
async def list_notes():
    return await db.get_all_notes()


@app.get("/notes/search")
async def search_notes(q: str = ""):
    if not q.strip():
        return await db.get_all_notes()
    return await db.search_notes(q)


@app.get("/notes/list")
async def list_notes_lightweight():
    """Lightweight note listing for the picker — id, title, updated_at, group_id.
    Must be declared BEFORE /notes/{note_id} so FastAPI doesn't capture
    'list' as a path parameter. group_id is included so the picker tree can
    nest notes under their parent group in a single round-trip."""
    notes = await db.get_all_notes()
    return [
        {
            "id": n["id"],
            "title": n["title"],
            "updated_at": n["updated_at"],
            "group_id": n.get("group_id"),
        }
        for n in notes
    ]


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


_UNSET = object()


@app.post("/notes")
async def create_note_route(body: dict):
    """Create a new empty note (independent of the audio-capture pipeline).

    Body shape:
      {"title"?: str, "content"?: str, "tags"?: list, "source"?: str,
       "group_id"?: str | null}

    Broadcasts {"type": "note", "note": ...} on the WS so other windows
    refresh immediately.
    """
    note = await db.create_note(
        title=(body.get("title") or "Untitled Note"),
        content=(body.get("content") or ""),
        tags=(body.get("tags") or []),
        source=(body.get("source") or ""),
        group_id=body.get("group_id"),
    )
    await broadcast({"type": "note", "note": note})
    return note


@app.put("/notes/{note_id}")
async def update_note_route(note_id: str, body: dict):
    """Partial update for a note (title / content / tags / source / group_id /
    canvas_state).

    Any field omitted from the body is left untouched. Pass `"group_id": null`
    to detach a note from its group. Pass `"canvas_state": null` to clear the
    canvas state (renderer falls back to the legacy `content` markdown).
    Broadcasts {"type": "note_updated", ...} so the React UI refreshes via
    useWebSocket.
    """
    kwargs = {}
    if "title" in body:
        kwargs["title"] = body["title"]
    if "content" in body:
        kwargs["content"] = body["content"]
    if "tags" in body:
        kwargs["tags"] = body["tags"]
    if "source" in body:
        kwargs["source"] = body["source"]
    if "group_id" in body:
        kwargs["group_id"] = body["group_id"]  # may be None to detach
    if "canvas_state" in body:
        kwargs["canvas_state"] = body["canvas_state"]  # may be None to clear

    note = await db.update_note(note_id, **kwargs)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    await broadcast({"type": "note_updated", "note": note})
    return note


# --------------------------- Groups -----------------------------------------


@app.get("/groups")
async def list_groups():
    """Return all groups (flat list, ordered by name). Hierarchy is
    reconstructed client-side from parent_id."""
    return await db.get_all_groups()


@app.post("/groups")
async def create_group_route(body: dict):
    """Create a group.

    Body shape: {"name": str, "parent_id"?: str | null}
    """
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    parent_id = body.get("parent_id")
    group = await db.create_group(name=name, parent_id=parent_id)
    await broadcast({"type": "group_created", "group": group})
    return group


@app.put("/groups/{group_id}")
async def update_group_route(group_id: str, body: dict):
    """Rename and/or reparent a group.

    Body shape: {"name"?: str, "parent_id"?: str | null}

    Rejects self-parenting and direct circular references. Doesn't fully
    walk the chain — a malicious client could still construct a cycle by
    swapping parents in two requests; we accept that for now (it'd only
    confuse the tree renderer, not corrupt data).
    """
    kwargs = {}
    if "name" in body:
        name = (body["name"] or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="name cannot be empty")
        kwargs["name"] = name
    if "parent_id" in body:
        if body["parent_id"] == group_id:
            raise HTTPException(
                status_code=400, detail="a group cannot be its own parent"
            )
        kwargs["parent_id"] = body["parent_id"]

    group = await db.update_group(group_id, **kwargs)
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    await broadcast({"type": "group_updated", "group": group})
    return group


@app.delete("/groups/{group_id}")
async def delete_group_route(group_id: str):
    """Delete a group; orphans child notes (group_id=NULL) and child
    subgroups (parent_id=NULL). Implemented as a manual cascade in
    database.delete_group()."""
    success = await db.delete_group(group_id)
    if success:
        await broadcast({"type": "group_deleted", "group_id": group_id})
    return {"success": success}


@app.post("/transcribe-push-to-talk")
async def transcribe_push_to_talk(
    file: UploadFile = File(...),
    mode: str = Form("rewrite"),
    note_id: str | None = Form(None),
    append: bool = Form(True),
):
    """Transcribe a short mic recording and optionally append it to a note.

    Form fields:
      file       — WAV audio blob recorded in the renderer (mono, 16kHz preferred)
      mode       — "rewrite" (Sub-project 4 default — AI restructure with sacred-
                    content preservation) or "verbatim" (aggressive cleanup
                    only, no restructuring). The renderer picks the mode based
                    on the hotkey: Ctrl+Space=rewrite, Shift+Ctrl+Space=verbatim.
      note_id    — target note to append to (required when append=true)
      append     — when true (default), append the polished text to the note
                   and broadcast `note_updated`. When false, just return the
                   transcript so the caller can do something else with it.

    Returns: {"text": <polished_markdown>, "raw": <raw_transcript>,
             "appended_to": <note_id_or_null>, "mode": <mode>}
    """
    if mode not in ("verbatim", "rewrite"):
        raise HTTPException(status_code=400, detail="mode must be 'verbatim' or 'rewrite'")

    wav_bytes = await file.read()
    if not wav_bytes:
        raise HTTPException(status_code=400, detail="empty audio file")

    # Stage 1: raw transcription. Reuse the same Whisper path as the wake-word
    # command pipeline (single-speaker, language-agnostic).
    try:
        raw_text = await asyncio.to_thread(
            ai_client.transcribe_audio, wav_bytes, False
        )
    except (OSError, RuntimeError, ValueError, OpenAIAPIError) as e:
        debug.error("routes", "dictation transcribe failed", e)
        raise HTTPException(
            status_code=500, detail=f"transcription failed: {e}"
        ) from e
    raw_text = (raw_text or "").strip()
    if not raw_text:
        return {"text": "", "raw": "", "appended_to": None, "mode": mode}

    # Voice modifier (Sub-project 4): a spoken "quote:" / "verbatim:" prefix
    # forces verbatim mode even when the hotkey requested rewrite, and is
    # stripped so the command word never lands in the saved note. This is the
    # voice half of the verbatim modifier; the hotkey half is Shift+Ctrl+Space
    # in the renderer.
    forced_mode, raw_text = ai_client.parse_voice_modifier(raw_text)
    if forced_mode:
        mode = forced_mode
        debug.log("routes", "voice modifier detected — forcing verbatim")
        if not raw_text:
            return {"text": "", "raw": "", "appended_to": None, "mode": mode}

    # Stage 2: polish via the chosen mode. Default is rewrite; the renderer
    # selects verbatim via Shift+Ctrl+Space, or the voice prefix above forces
    # it. The mode is always explicit (matches the "explicit user control"
    # preference from CLAUDE.md).
    lang = language_state.get_language()
    target_code = lang.get("code") if lang else None
    target_label = lang.get("label") if lang else None
    try:
        if mode == "verbatim":
            polished = await asyncio.to_thread(
                ai_client.polish_verbatim_aggressive,
                raw_text, target_code, target_label,
            )
        else:  # "rewrite"
            polished = await asyncio.to_thread(
                ai_client.rewrite_dictation,
                raw_text, target_code, target_label,
            )
    except (OSError, RuntimeError, ValueError, OpenAIAPIError) as e:
        debug.error("routes", "dictation polish failed", e)
        raise HTTPException(
            status_code=500, detail=f"polish failed: {e}"
        ) from e

    polished = (polished or raw_text).strip()
    appended_to = None
    if append:
        if not note_id:
            raise HTTPException(
                status_code=400,
                detail="append=true requires note_id",
            )
        # Soft separator (\n\n) for dictation appends — not a horizontal rule.
        # The append_to_note default still produces a `---` divider for
        # capture-pipeline writes; we override it here.
        updated = await db.append_to_note(note_id, polished, separator="\n\n")
        if updated is None:
            raise HTTPException(status_code=404, detail="Note not found")
        appended_to = note_id
        await broadcast({"type": "note_updated", "note": updated})

    return {
        "text": polished,
        "raw": raw_text,
        "appended_to": appended_to,
        "mode": mode,
    }


@app.get("/tts/say")
async def tts_say(text: str = ""):
    """Sub-project 4: 1-second hear-back synthesis.

    Renderer calls this after a successful capture so the user gets a spoken
    "Saved to <note>" without looking at the screen. Returns a `audio/wav`
    body. Hear-back is best-effort: when Kokoro isn't installed or the model
    file is missing we return a 503 so the renderer can no-op gracefully —
    crashing the save path here would be worse than skipping the cue.

    The 200-char cap is a guard against accidental long inputs; the
    confirmation phrases the spec describes are <30 chars.
    """
    phrase = (text or "").strip()
    if not phrase:
        return Response(content=b"", media_type="audio/wav")
    if len(phrase) > 200:
        phrase = phrase[:200]

    try:
        wav = await asyncio.to_thread(tts_kokoro.synthesize_to_wav, phrase)
    except tts_kokoro.TTSUnavailable as e:
        # Best-effort: 503 (Service Unavailable) is the right signal to the
        # renderer that this is a no-op condition, not a hard error.
        raise HTTPException(status_code=503, detail=f"TTS unavailable: {e}") from e
    return Response(content=wav, media_type="audio/wav")


@app.post("/trigger")
async def trigger_note():
    """Trigger note capture via keyboard shortcut or UI button."""
    if _trigger_callback:
        import threading
        threading.Thread(target=_trigger_callback, daemon=True).start()
        return {"success": True, "message": "Note capture triggered"}
    return {"success": False, "message": "Trigger callback not set"}


async def _target_payload() -> dict:
    """Build the WebSocket / HTTP target payload. Includes the target note's
    title (resolved live from the DB) so the bubble label can render without
    a separate fetch. Falls back to None on title if the note was deleted."""
    state = target_state.get_target()
    title = None
    if state["note_id"]:
        note = await db.get_note(state["note_id"])
        if note is None:
            # Target note was deleted while pinned — reset to default.
            target_state.clear_target()
            state = target_state.get_target()
        else:
            title = note["title"]
    return {
        "type": "target",
        "note_id": state["note_id"],
        "create_new_pending": state["create_new_pending"],
        "title": title,
    }


@app.get("/target")
async def get_target():
    """Return the current note routing target for the bubble + picker."""
    return await _target_payload()


@app.post("/target")
async def set_target(body: dict):
    """Update the routing target.

    Body shapes:
      {"note_id": "<id>"}                        -> pin to existing note
      {"note_id": null, "create_new_pending": true}  -> create new on next capture
      {"note_id": null}                          -> clear target (default behavior)
    """
    note_id = body.get("note_id")
    create_new_pending = bool(body.get("create_new_pending", False))

    if note_id:
        target_state.set_target(note_id)
    elif create_new_pending:
        target_state.set_create_new_pending()
    else:
        target_state.clear_target()

    payload = await _target_payload()
    await broadcast(payload)
    return payload


@app.get("/language")
async def get_language_route():
    """Return the current output-language preference for the picker."""
    return language_state.get_language()


@app.post("/language")
async def set_language_route(body: dict):
    """Update the output-language preference.

    Body shape:
      {"code": "<iso>", "label": "<display>", "emoji": "<single-char>"}
      {"code": "auto", "label": "Global", "emoji": "🌍"}  -> back to default

    Re-broadcasts to WS so any other window tracking the choice updates
    immediately.
    """
    code = (body.get("code") or "auto").strip() or "auto"
    label = (body.get("label") or "Global").strip() or "Global"
    emoji = (body.get("emoji") or "\U0001F30D").strip() or "\U0001F30D"
    new_state = language_state.set_language(code, label, emoji)
    await broadcast({"type": "language", **new_state})
    return new_state


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
