"""
Wake word listener for "Hey Deen" using Picovoice Porcupine.

Exposes start_wake_word_listener(on_wake, stop_event) — same signature as the
old openWakeWord implementation, so main.py doesn't need to change.
"""
import os
import struct
import sysconfig
import threading
import time
from pathlib import Path

from config import (
    PICOVOICE_ACCESS_KEY,
    PORCUPINE_SENSITIVITY,
    WAKE_WORD_MODEL,
)

COOLDOWN_SEC = 1.5


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
):
    """
    Listen for the "Hey Deen" wake word using Picovoice Porcupine and call
    on_wake() when detected. Falls back gracefully if unavailable.
    """
    if not PICOVOICE_ACCESS_KEY:
        print("[WakeWord] PICOVOICE_ACCESS_KEY missing in .env")
        print("[WakeWord] Get one (free for personal use) at https://console.picovoice.ai/")
        print("[WakeWord] Use Ctrl+Shift+N or the app button to capture notes meanwhile.")
        stop_event.wait()
        return

    model_path = Path(WAKE_WORD_MODEL)
    if not model_path.exists():
        print(f"[WakeWord] Wake word file not found at {model_path}")
        print("[WakeWord] Train a custom wake word at https://console.picovoice.ai/ "
              "and drop the .ppn file there.")
        stop_event.wait()
        return

    try:
        import pvporcupine
    except (ImportError, OSError) as e:
        print(f"[WakeWord] pvporcupine not available: {e}")
        print("[WakeWord] Run: pip install pvporcupine>=4.0.0,<5.0.0")
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

        print(f"[WakeWord] Porcupine v{porcupine.version} listening for 'Hey Deen' "
              f"(sensitivity={PORCUPINE_SENSITIVITY}, mic='{default_mic['name']}')")

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

            print("[WakeWord] 'Hey Deen' detected!")
            last_trigger_time = now
            on_wake()

    except (OSError, RuntimeError) as e:
        print(f"[WakeWord] Failed to start: {e}")
        print("[WakeWord] Use the keyboard shortcut (Ctrl+Shift+N) or the app button instead.")
        stop_event.wait()
    except Exception as e:
        # pvporcupine raises subclassed exceptions for invalid keys, expired licenses, etc.
        err_name = type(e).__name__
        print(f"[WakeWord] Unexpected error ({err_name}): {e}")
        if "Activation" in err_name or "AccessKey" in str(e):
            print("[WakeWord] Check your PICOVOICE_ACCESS_KEY at https://console.picovoice.ai/")
        stop_event.wait()
    finally:
        if mic_stream is not None:
            try:
                mic_stream.stop_stream()
                mic_stream.close()
            except Exception:
                pass
        if p is not None:
            try:
                p.terminate()
            except Exception:
                pass
        if porcupine is not None:
            try:
                porcupine.delete()
            except Exception:
                pass
