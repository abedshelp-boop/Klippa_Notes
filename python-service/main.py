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
from mic_listener import record_command
from wake_word import start_wake_word_listener
from note_generator import process_note
from media_control import pause_media_if_playing, resume_media
from routes import app, broadcast, set_trigger_callback
import video_context

ring_buffer = RingBuffer()
stop_event = threading.Event()

_server_loop = None
_processing_lock = threading.Lock()


def _broadcast_sync(message: dict):
    """Broadcast a message to all WebSocket clients from a non-async thread."""
    if _server_loop:
        asyncio.run_coroutine_threadsafe(broadcast(message), _server_loop)


def on_wake_word_detected():
    """Called when the wake word is detected or trigger endpoint is hit."""
    if not _processing_lock.acquire(blocking=False):
        print("[Main] Already processing a note, skipping.")
        return

    media_was_paused = False
    try:
        print("[Main] Hey Deen! Listening for your command...")
        _broadcast_sync({"type": "status", "status": "command"})

        frozen_video = video_context.get_video()

        media_was_paused = pause_media_if_playing(ring_buffer)

        try:
            command_audio = record_command()
        except Exception as e:
            print(f"[Main] Mic recording failed: {e}")
            command_audio = None

        # User said "Hey Deen" but then said nothing — abort the whole note.
        if command_audio is None:
            print("[Main] User said nothing after wake word — canceling note.")
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
            print("[Main] No system audio captured yet, skipping.")
            if media_was_paused:
                resume_media()
            _broadcast_sync({"type": "status", "status": "listening"})
            return

        rms = float(np.sqrt(np.mean(system_audio ** 2)))
        if rms < MEDIA_DETECT_THRESHOLD:
            print(f"[Main] System audio too quiet (RMS={rms:.6f}), "
                  f"nothing meaningful to transcribe. Skipping.")
            if media_was_paused:
                resume_media()
            _broadcast_sync({"type": "status", "status": "listening"})
            return

        print(f"[Main] Captured {len(system_audio)} system audio samples "
              f"({len(system_audio) / 16000:.1f}s raw). Processing...")

        if _server_loop:
            asyncio.run_coroutine_threadsafe(
                process_note(system_audio, command_audio, broadcast,
                             media_was_paused=media_was_paused,
                             video_info=frozen_video),
                _server_loop,
            )
    finally:
        _processing_lock.release()


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


def start_wake_word_thread():
    t = threading.Thread(
        target=start_wake_word_listener,
        args=(on_wake_word_detected, stop_event),
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

    print("=" * 50)
    print("  DEEN-NOTES - Voice-Activated Note Taker")
    print("=" * 50)
    print()

    try:
        _wait_for_port(FASTAPI_HOST, FASTAPI_PORT, timeout=15)
    except RuntimeError as e:
        print(f"[Main] {e}")
        print("[Main] Another instance may be running. Exiting.")
        sys.exit(1)

    set_trigger_callback(on_wake_word_detected)

    try:
        audio_thread = start_audio_thread()
        print("[Main] System audio capture started.")
    except Exception as e:
        print(f"[Main] Audio capture failed: {e}")
        print("[Main] System audio capture disabled.")

    try:
        wake_thread = start_wake_word_thread()
        print("[Main] Wake word listener started.")
    except Exception as e:
        print(f"[Main] Wake word failed: {e}")

    config = uvicorn.Config(
        app,
        host=FASTAPI_HOST,
        port=FASTAPI_PORT,
        log_level="warning",
    )
    server = DeenServer(config)

    print(f"[Main] API server starting on http://{FASTAPI_HOST}:{FASTAPI_PORT}")
    print()
    print("Say 'Hey Deen' or press Ctrl+Shift+N to capture a note.")
    print()

    def shutdown(signum=None, frame=None):
        print("\n[Main] Shutting down...")
        stop_event.set()
        server.should_exit = True

    signal.signal(signal.SIGINT, shutdown)
    try:
        signal.signal(signal.SIGTERM, shutdown)
    except (OSError, ValueError):
        pass

    loop = asyncio.new_event_loop()
    _server_loop = loop
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(server.serve())
    except Exception as e:
        print(f"[Main] Server error: {e}")
    finally:
        stop_event.set()
        loop.close()
        print("[Main] Goodbye!")


if __name__ == "__main__":
    main()
