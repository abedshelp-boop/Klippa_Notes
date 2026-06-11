"""
Deen-Notes Python Service — Entry Point

Starts three concurrent subsystems:
1. System audio capture (WASAPI loopback -> ring buffer)
2. Wake word listener (microphone -> Porcupine "Hey Deen")
3. FastAPI server (REST + WebSocket for Electron UI)
"""

import asyncio
import threading
import sys
import signal

import uvicorn

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import numpy as np
from config import (
    BUFFER_DURATION_SEC,
    FASTAPI_HOST,
    FASTAPI_PORT,
    MEDIA_DETECT_THRESHOLD,
)
from buffer import RingBuffer
from debug import debug
from mic_listener import record_command
from wake_word import start_wake_word_listener
from note_generator import process_note
from media_control import pause_media_if_playing, resume_media
from routes import app, broadcast, set_trigger_callback
import target as target_state
import language as language_state

ring_buffer = RingBuffer()
stop_event = threading.Event()

_server_loop = None
_processing_lock = threading.Lock()

MAX_DISAMBIGUATION_RETRIES = 1  # one extra attempt after the first miss


def _broadcast_sync(message: dict):
    """Broadcast a message to all WebSocket clients from a non-async thread."""
    if _server_loop:
        asyncio.run_coroutine_threadsafe(broadcast(message), _server_loop)


def run_disambiguation_loop(decision, quick_inbox_id: str):
    """Voice-only disambiguation: speak the question, listen for a reply,
    parse yes/no/named, retry once, then fall through to Quick Inbox.

    Returns a RoutingDecision that's always `existing` or `create_new` —
    caller can save without further prompting.
    """
    import voice_routing
    import tts_client
    import ai_client
    from resampler import audio_to_wav_bytes

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
            debug.warn(
                "Disamb",
                "no reply, retrying" if attempt == 0 else "still no reply",
            )
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
            if current.candidates:
                return voice_routing.RoutingDecision(
                    kind="existing",
                    note_id=current.candidates[0]["id"],
                    content=current.content,
                    confidence="medium",
                )
            # No candidates → it was the "create one?" prompt. Extract the
            # proposed title from the question text.
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
            break  # user rejected — stop looping
        # unclear → next iteration (if any retries left)

    tts_client.say("Saved to Quick Inbox — couldn't tell where you meant.")
    return voice_routing.RoutingDecision(
        kind="existing",
        note_id=quick_inbox_id,
        content=current.content,
        confidence="low",
    )


def on_wake_word_detected():
    """Called when the wake word is detected or trigger endpoint is hit."""
    # Step-1 diagnostic: mark entry so we can see in logs which event triggered
    # this (wake-word listener vs /trigger HTTP endpoint) and at what time.
    debug.log("Main", "on_wake_word_detected ENTRY")
    if not _processing_lock.acquire(blocking=False):
        debug.log("Main", "already processing, skipping")
        return

    media_was_paused = False
    try:
        debug.log("Main", "listening for command")
        _broadcast_sync({"type": "status", "status": "command"})

        # Snapshot target at capture-time so a mid-capture picker change
        # can't redirect a note in flight.
        frozen_target = target_state.get_target()
        # Same reasoning for language — mid-capture picker swap shouldn't
        # retroactively translate a note already mid-flight.
        frozen_language = language_state.get_language()

        media_was_paused = pause_media_if_playing(ring_buffer)
        debug.log("Main", "media_was_paused", media_was_paused)

        try:
            command_audio = record_command()
        except (OSError, RuntimeError) as e:
            debug.error("Main", "mic recording failed", e)
            command_audio = None

        # User said "Hey Deen" but then said nothing — abort the whole note.
        if command_audio is None:
            debug.log("Main", "user said nothing — canceling note")
            if media_was_paused:
                resume_media()
            _broadcast_sync({"type": "status", "status": "listening"})
            return

        # Read the full ring buffer rather than a fixed 300s slice — the VAD
        # step inside process_note() trims this down to speech-only, so there
        # is no benefit to pre-trimming here and a big downside for short
        # content (a 60s Short would lose nothing; a 10-min lecture would
        # lose its opening).
        system_audio = ring_buffer.read_last(BUFFER_DURATION_SEC)

        if len(system_audio) == 0:
            debug.log("Main", "no system audio captured yet, skipping")
            if media_was_paused:
                resume_media()
            _broadcast_sync({"type": "status", "status": "listening"})
            return

        rms = float(np.sqrt(np.mean(system_audio ** 2)))
        if rms < MEDIA_DETECT_THRESHOLD:
            debug.log(
                "Main",
                "system audio too quiet — skipping",
                {"rms": rms, "threshold": MEDIA_DETECT_THRESHOLD},
            )
            if media_was_paused:
                resume_media()
            _broadcast_sync({"type": "status", "status": "listening"})
            return

        debug.log(
            "Main",
            "captured samples, processing",
            {
                "samples": len(system_audio),
                "duration_sec": len(system_audio) / 16000,
            },
        )

        # Voice routing — pre-transcribe the command and decide destination
        # BEFORE dispatching the heavy process_note pipeline. This lets us
        # emit disambiguation prompts early without making the user wait.
        command_text = ""
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
                quick_inbox_id, routing_decision = fut.result(timeout=10)
            except Exception as e:  # noqa: BLE001 — degrade for any routing failure
                debug.warn("Main", "routing decide failed", e)
                routing_decision = None

            if (routing_decision is not None
                    and routing_decision.kind == "needs_voice_followup"):
                routing_decision = run_disambiguation_loop(
                    routing_decision, quick_inbox_id
                )

            asyncio.run_coroutine_threadsafe(
                process_note(system_audio, command_audio, broadcast,
                             media_was_paused=media_was_paused,
                             target=frozen_target,
                             language=frozen_language,
                             routing_decision=routing_decision,
                             quick_inbox_id=quick_inbox_id),
                _server_loop,
            )
            debug.log(
                "Main",
                "process_note dispatched",
                {"media_was_paused": media_was_paused,
                 "routing_kind": (routing_decision.kind if routing_decision else None)},
            )
        else:
            debug.warn(
                "Main",
                "_server_loop is None — process_note NOT dispatched",
                {"media_was_paused": media_was_paused},
            )
    finally:
        _processing_lock.release()
        debug.log(
            "Main",
            "on_wake_word_detected FINALLY: lock released",
            {"media_was_paused": media_was_paused},
        )


def start_audio_thread():
    from audio_capture import start_system_audio_capture
    t = threading.Thread(
        target=start_system_audio_capture,
        args=(ring_buffer, stop_event),
        daemon=True,
        name="audio-capture",
    )
    t.start()
    return t


def _on_wake_word_state_change(state: dict):
    """Bridge wake-word state changes onto the WebSocket so the bubble can
    show "wake-word offline" the moment the listener gives up, instead of
    pretending it's alive forever."""
    _broadcast_sync({
        "type": "wake_word_state",
        "status": state.get("status"),
        "error": state.get("error"),
    })


def start_wake_word_thread():
    t = threading.Thread(
        target=start_wake_word_listener,
        args=(on_wake_word_detected, stop_event, _on_wake_word_state_change),
        daemon=True,
        name="wake-word",
    )
    t.start()
    return t


class DeenServer(uvicorn.Server):
    def install_signal_handlers(self):
        pass


def _wait_for_port(host, port, timeout=10):
    """Wait until the port is free, or raise after timeout."""
    import socket
    import time
    start = time.time()
    while time.time() - start < timeout:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind((host, port))
            sock.close()
            return
        except OSError:
            sock.close()
            time.sleep(0.5)
    raise RuntimeError(f"Port {port} still in use after {timeout}s")


def main():
    global _server_loop

    debug.log("service", "started", "DEEN-NOTES Voice-Activated Note Taker")

    try:
        _wait_for_port(FASTAPI_HOST, FASTAPI_PORT, timeout=15)
    except RuntimeError as e:
        debug.error("Main", "port already in use", e)
        debug.error("Main", "another instance may be running — exiting")
        sys.exit(1)

    set_trigger_callback(on_wake_word_detected)

    try:
        audio_thread = start_audio_thread()
        debug.log("Main", "system audio capture started")
    except (OSError, RuntimeError, ImportError) as e:
        debug.error("Main", "audio capture failed", e)
        debug.warn("Main", "system audio capture disabled")

    try:
        wake_thread = start_wake_word_thread()
        debug.log("Main", "wake word listener started")
    except (OSError, RuntimeError, ImportError) as e:
        debug.error("Main", "wake word failed", e)

    config = uvicorn.Config(
        app,
        host=FASTAPI_HOST,
        port=FASTAPI_PORT,
        log_level="warning",
    )
    server = DeenServer(config)

    debug.log(
        "Main",
        "API server starting",
        {"url": f"http://{FASTAPI_HOST}:{FASTAPI_PORT}"},
    )

    def shutdown(signum=None, frame=None):
        debug.log("Main", "shutting down")
        stop_event.set()
        server.should_exit = True

    signal.signal(signal.SIGINT, shutdown)
    try:
        signal.signal(signal.SIGTERM, shutdown)
    except (OSError, ValueError):
        # Deliberate: signal.SIGTERM isn't supported on Windows; falling
        # back to Ctrl+C only is intentional. Fires once at boot on every
        # Windows launch — a log here would just be noise.
        pass

    loop = asyncio.new_event_loop()
    _server_loop = loop
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(server.serve())
    except (OSError, RuntimeError) as e:
        debug.error("Main", "server error", e)
        raise
    finally:
        stop_event.set()
        loop.close()
        debug.log("Main", "goodbye")


if __name__ == "__main__":
    main()
