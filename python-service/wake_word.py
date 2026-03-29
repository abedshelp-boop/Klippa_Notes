import threading
import time
import collections
import numpy as np
from pathlib import Path

from config import WAKE_WORD_MODEL, WAKE_WORD_THRESHOLD, WAKE_WORD_PEAK_THRESHOLD, MIC_GAIN

SCORE_WINDOW_SIZE = 2
COOLDOWN_SEC = 2.0
TARGET_RMS = 3000


def start_wake_word_listener(
    on_wake: callable,
    stop_event: threading.Event,
):
    """
    Listen for the "Hey Klippa" wake word using openWakeWord and call
    on_wake() when detected. Falls back gracefully if unavailable.
    """
    model_path = Path(WAKE_WORD_MODEL)
    if not model_path.exists():
        print(f"[WakeWord] Model not found at {model_path}")
        print("[WakeWord] Use the keyboard shortcut (Ctrl+Shift+N) or the app button instead.")
        stop_event.wait()
        return

    try:
        from openwakeword.model import Model
    except (ImportError, OSError) as e:
        print(f"[WakeWord] openWakeWord not available: {e}")
        print("[WakeWord] Use the keyboard shortcut (Ctrl+Shift+N) or the app button instead.")
        stop_event.wait()
        return

    mic_stream = None

    try:
        import pyaudiowpatch as pyaudio
        import openwakeword

        openwakeword.utils.download_models()

        p = pyaudio.PyAudio()

        try:
            import speexdsp_ns  # noqa: F401
            use_speex = True
        except ImportError:
            use_speex = False

        oww_model = Model(
            wakeword_models=[str(model_path)],
            inference_framework="onnx",
            enable_speex_noise_suppression=use_speex,
        )

        CHUNK = 1280
        RATE = 16000

        default_mic = p.get_default_input_device_info()
        mic_stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=RATE,
            input=True,
            input_device_index=default_mic["index"],
            frames_per_buffer=CHUNK,
        )

        ns_label = "on" if use_speex else "off (speexdsp_ns not available)"
        print(f"[WakeWord] Listening for 'Hey Klippa' (avg_threshold={WAKE_WORD_THRESHOLD}, "
              f"peak_threshold={WAKE_WORD_PEAK_THRESHOLD}, window={SCORE_WINDOW_SIZE}, "
              f"mic_gain={MIC_GAIN}, noise_suppression={ns_label})...")

        score_history: dict[str, collections.deque] = {}
        last_trigger_time = 0.0

        while not stop_event.is_set():
            audio = np.frombuffer(
                mic_stream.read(CHUNK, exception_on_overflow=False),
                dtype=np.int16,
            )

            audio_float = audio.astype(np.float32) * MIC_GAIN
            rms = np.sqrt(np.mean(audio_float ** 2))
            if rms > 1.0:
                scale = TARGET_RMS / rms
                audio_float *= scale
            audio = np.clip(audio_float, -32768, 32767).astype(np.int16)

            predictions = oww_model.predict(audio)

            for model_name, score in predictions.items():
                if model_name not in score_history:
                    score_history[model_name] = collections.deque(maxlen=SCORE_WINDOW_SIZE)
                score_history[model_name].append(score)

                avg_score = sum(score_history[model_name]) / len(score_history[model_name])
                peak_hit = score >= WAKE_WORD_PEAK_THRESHOLD
                avg_hit = avg_score > WAKE_WORD_THRESHOLD

                if peak_hit or avg_hit:
                    now = time.monotonic()
                    if now - last_trigger_time < COOLDOWN_SEC:
                        continue

                    trigger = "peak" if peak_hit else "avg"
                    print(f"[WakeWord] 'Hey Klippa' detected! "
                          f"(trigger={trigger}, avg={avg_score:.3f}, raw={score:.3f})")
                    last_trigger_time = now
                    score_history[model_name].clear()
                    oww_model.reset()
                    on_wake()

    except (OSError, RuntimeError) as e:
        print(f"[WakeWord] Failed to start: {e}")
        print("[WakeWord] Use the keyboard shortcut (Ctrl+Shift+N) or the app button instead.")
        stop_event.wait()
    except Exception as e:
        print(f"[WakeWord] Unexpected error: {e}")
    finally:
        if mic_stream:
            try:
                mic_stream.stop_stream()
                mic_stream.close()
            except Exception:
                pass
