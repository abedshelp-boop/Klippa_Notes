"""
Wake word listener for "Hey Deen" using Picovoice Porcupine.

Exposes start_wake_word_listener(on_wake, stop_event, on_state_change=None)
and get_wake_word_state() so the rest of the app can tell whether the wake
word is actually listening or has silently failed at startup.
"""
import os
import struct
import sysconfig
import threading
import time
import traceback
from pathlib import Path

from config import (
    PICOVOICE_ACCESS_KEY,
    PORCUPINE_SENSITIVITY,
    WAKE_WORD_MODEL,
)
from debug import debug

COOLDOWN_SEC = 1.5

# Module-level state so /health and the WebSocket broadcaster can read it.
# Status values:
#   "not_started"  — start_wake_word_listener never ran
#   "initializing" — entered the try block, Porcupine/Mic init in progress
#   "listening"    — main detection loop is running (the "actually alive" state)
#   "failed"       — gave up; reason in `error`
_state = {"status": "not_started", "error": None}
_state_lock = threading.Lock()
_state_callback = None  # optional callable(dict) fired on every transition


def get_wake_word_state() -> dict:
    """Return a copy of the current wake-word state (status + error)."""
    with _state_lock:
        return dict(_state)


def _set_state(status: str, error: str | None = None) -> None:
    with _state_lock:
        _state["status"] = status
        _state["error"] = error
        snapshot = dict(_state)
    cb = _state_callback
    if cb is not None:
        try:
            cb(snapshot)
        except (TypeError, RuntimeError) as e:
            debug.error("WakeWord", "state callback raised", e)


def _resolve_porcupine_library_path() -> str | None:
    """
    Pick the Porcupine native library that matches the *Python interpreter's*
    architecture, not the OS architecture. This matters on ARM64 Windows where
    the user is running x64 Python in emulation: pvporcupine's auto-detection
    looks at the OS (`platform.machine() == 'ARM64'`) and picks the arm64 .dll,
    which then fails to load with "not a valid Win32 application".

    Returns None on non-Windows so pvporcupine's default resolution is used.
    """
    import pvporcupine

    pkg_dir = os.path.dirname(pvporcupine.__file__)
    plat = sysconfig.get_platform()  # e.g. 'win-amd64', 'win-arm64'

    if plat == "win-amd64":
        return os.path.join(pkg_dir, "lib", "windows", "amd64", "libpv_porcupine.dll")
    if plat == "win-arm64":
        return os.path.join(pkg_dir, "lib", "windows", "arm64", "libpv_porcupine.dll")

    # Linux/macOS or unknown — let pvporcupine handle it.
    return None


def start_wake_word_listener(
    on_wake: callable,
    stop_event: threading.Event,
    on_state_change: callable | None = None,
):
    """
    Listen for the "Hey Deen" wake word using Picovoice Porcupine and call
    on_wake() when detected. Falls back gracefully if unavailable.

    on_state_change(state_dict) fires whenever the listener transitions
    between not_started / initializing / listening / failed. Used by main.py
    to broadcast a `wake_word_state` message over the WebSocket.
    """
    global _state_callback
    _state_callback = on_state_change
    _set_state("initializing")

    if not PICOVOICE_ACCESS_KEY:
        msg = "PICOVOICE_ACCESS_KEY missing in .env"
        debug.warn("WakeWord", msg)
        debug.warn(
            "WakeWord",
            "get a key (free for personal use) at https://console.picovoice.ai/",
        )
        debug.warn(
            "WakeWord",
            "use Ctrl+Shift+N or the app button to capture notes meanwhile",
        )
        _set_state("failed", msg)
        stop_event.wait()
        return

    model_path = Path(WAKE_WORD_MODEL)
    if not model_path.exists():
        msg = f"Wake word file not found at {model_path}"
        debug.warn("WakeWord", msg)
        debug.warn(
            "WakeWord",
            "train a custom wake word at https://console.picovoice.ai/ and drop the .ppn file there",
        )
        _set_state("failed", msg)
        stop_event.wait()
        return

    try:
        import pvporcupine
    except (ImportError, OSError) as e:
        msg = f"pvporcupine not available: {e}"
        debug.warn("WakeWord", msg)
        debug.warn("WakeWord", "run: pip install pvporcupine>=4.0.0,<5.0.0")
        _set_state("failed", msg)
        stop_event.wait()
        return

    porcupine = None
    mic_stream = None
    p = None

    try:
        import pyaudiowpatch as pyaudio

        library_path = _resolve_porcupine_library_path()
        porcupine = pvporcupine.create(
            access_key=PICOVOICE_ACCESS_KEY,
            keyword_paths=[str(model_path)],
            sensitivities=[PORCUPINE_SENSITIVITY],
            library_path=library_path,  # None == use pvporcupine default
        )

        sample_rate = porcupine.sample_rate      # 16000
        frame_length = porcupine.frame_length    # 512

        p = pyaudio.PyAudio()
        default_mic = p.get_default_input_device_info()

        mic_stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=sample_rate,
            input=True,
            input_device_index=default_mic["index"],
            frames_per_buffer=frame_length,
        )

        debug.log(
            "WakeWord",
            "Porcupine listening for 'Hey Deen'",
            {
                "sensitivity": PORCUPINE_SENSITIVITY,
                "mic": default_mic["name"],
                "rate": sample_rate,
            },
        )
        _set_state("listening")

        last_trigger_time = 0.0
        unpack_fmt = "h" * frame_length

        while not stop_event.is_set():
            raw = mic_stream.read(frame_length, exception_on_overflow=False)
            pcm = struct.unpack_from(unpack_fmt, raw)

            keyword_index = porcupine.process(pcm)
            if keyword_index < 0:
                continue

            now = time.monotonic()
            if now - last_trigger_time < COOLDOWN_SEC:
                continue

            debug.log("WakeWord", "'Hey Deen' detected")
            last_trigger_time = now
            on_wake()

        # Step-1 diagnostic: confirm whether the loop ever exits cleanly via
        # stop_event vs. silently dying inside an except. If we see this line
        # after a crash report, we know the loop ran to completion and the
        # bubble-red came from somewhere else.
        debug.log(
            "WakeWord",
            "listen loop exited normally",
            {"stop_event_set": stop_event.is_set()},
        )

    except (OSError, RuntimeError) as e:
        msg = f"{type(e).__name__}: {e}"
        debug.error("WakeWord", "failed to start", msg)
        debug.error("WakeWord", "traceback", traceback.format_exc())
        debug.warn(
            "WakeWord",
            "use the keyboard shortcut (Ctrl+Shift+N) or the app button instead",
        )
        _set_state("failed", msg)
        stop_event.wait()
    except Exception as e:
        # Deliberate catch-all: Picovoice raises non-public exception classes
        # (PorcupineActivationError, PorcupineInvalidArgumentError, etc.) we
        # can't reliably import without coupling tightly to a private API.
        # Narrow if pvporcupine exposes a public exception base.
        err_name = type(e).__name__
        msg = f"{err_name}: {e}"
        debug.error("WakeWord", "unexpected error", msg)
        debug.error("WakeWord", "traceback", traceback.format_exc())
        if "Activation" in err_name or "AccessKey" in str(e):
            debug.warn(
                "WakeWord",
                "check your PICOVOICE_ACCESS_KEY at https://console.picovoice.ai/",
            )
        _set_state("failed", msg)
        stop_event.wait()
    finally:
        # Cleanup paths swallow OSError/RuntimeError because each subsystem
        # may already be torn down by the time we get here (e.g. a partial
        # init that failed before we set the variable). Errors during
        # cleanup never need to propagate; debug.error would be noise.
        if mic_stream is not None:
            try:
                mic_stream.stop_stream()
                mic_stream.close()
            except (OSError, RuntimeError):
                pass
        if p is not None:
            try:
                p.terminate()
            except (OSError, RuntimeError):
                pass
        if porcupine is not None:
            try:
                porcupine.delete()
            except (OSError, RuntimeError):
                pass
