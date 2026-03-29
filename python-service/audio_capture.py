import threading
import time
import numpy as np
import pyaudiowpatch as pyaudio
from scipy.signal import resample_poly
from math import gcd

from buffer import RingBuffer
from config import SAMPLE_RATE

DEVICE_CHECK_INTERVAL_SEC = 3


def _find_default_loopback(p: pyaudio.PyAudio):
    """Find the WASAPI loopback device that corresponds to the current
    default output device (speakers, headphones, etc.)."""
    try:
        wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
    except OSError:
        raise RuntimeError("WASAPI not available on this system")

    default_idx = wasapi_info["defaultOutputDevice"]
    default_dev = p.get_device_info_by_index(default_idx)
    default_name = default_dev["name"]

    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        if (dev.get("isLoopbackDevice")
                and dev.get("maxInputChannels", 0) > 0
                and default_name in dev["name"]):
            return dev, default_name

    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        if dev.get("isLoopbackDevice") and dev.get("maxInputChannels", 0) > 0:
            return dev, default_name

    raise RuntimeError(
        "No WASAPI loopback device found. Make sure audio is enabled on your system."
    )


def _get_current_default_output_name(p: pyaudio.PyAudio):
    """Return the name of the current default WASAPI output device, or None."""
    try:
        wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_idx = wasapi_info["defaultOutputDevice"]
        return p.get_device_info_by_index(default_idx)["name"]
    except Exception:
        return None


def start_system_audio_capture(ring_buffer: RingBuffer, stop_event: threading.Event):
    """Capture system audio via WASAPI loopback, automatically switching
    when the default output device changes (e.g. headphones plugged in)."""
    while not stop_event.is_set():
        p = pyaudio.PyAudio()

        try:
            device, output_name = _find_default_loopback(p)
        except RuntimeError as e:
            print(f"[Audio] {e}")
            print(f"[Audio] Retrying in {DEVICE_CHECK_INTERVAL_SEC}s...")
            p.terminate()
            stop_event.wait(DEVICE_CHECK_INTERVAL_SEC)
            continue

        device_rate = int(device["defaultSampleRate"])
        device_channels = max(int(device.get("maxInputChannels", 2)), 1)
        frames_per_buffer = 512

        g = gcd(device_rate, SAMPLE_RATE)
        up = SAMPLE_RATE // g
        down = device_rate // g

        print(f"[Audio] Default output device: {output_name}")
        print(f"[Audio] Opening loopback: {device['name']} "
              f"(idx={device['index']}, rate={device_rate}Hz, ch={device_channels})")

        try:
            stream = p.open(
                format=pyaudio.paInt16,
                channels=device_channels,
                rate=device_rate,
                input=True,
                input_device_index=device["index"],
                frames_per_buffer=frames_per_buffer,
            )
        except OSError as e:
            print(f"[Audio] Failed to open loopback stream: {e}")
            print("[Audio] This can happen if no audio output device is active.")
            p.terminate()
            stop_event.wait(DEVICE_CHECK_INTERVAL_SEC)
            continue

        print(f"[Audio] Capturing system audio -> {SAMPLE_RATE}Hz mono")

        last_check = time.monotonic()

        while not stop_event.is_set():
            try:
                raw = stream.read(frames_per_buffer, exception_on_overflow=False)
                audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

                if device_channels > 1:
                    audio = audio.reshape(-1, device_channels).mean(axis=1)

                if device_rate != SAMPLE_RATE:
                    audio = resample_poly(audio, up, down).astype(np.float32)

                ring_buffer.write(audio)

                now = time.monotonic()
                if now - last_check >= DEVICE_CHECK_INTERVAL_SEC:
                    last_check = now
                    check_p = pyaudio.PyAudio()
                    try:
                        new_name = _get_current_default_output_name(check_p)
                        if new_name and new_name != output_name:
                            print(f"[Audio] Output device changed: "
                                  f"'{output_name}' -> '{new_name}'")
                            print("[Audio] Switching loopback capture...")
                            break
                    finally:
                        check_p.terminate()

            except OSError:
                print("[Audio] Stream error (device may have disconnected). "
                      "Reconnecting...")
                break
            except Exception as e:
                print(f"[Audio] Error: {e}")
                time.sleep(0.5)

        try:
            stream.stop_stream()
            stream.close()
        except Exception:
            pass
        p.terminate()

    print("[Audio] System audio capture stopped.")
