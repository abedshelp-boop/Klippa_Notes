"""
Media Control — Pause/resume system media via the Windows media play/pause key.

Uses ctypes to simulate VK_MEDIA_PLAY_PAUSE (0xB3), which is handled by
Chrome, Spotify, VLC, Windows Media Player, and most other media apps.
Audio-activity detection relies on the existing WASAPI loopback ring buffer.
"""

import ctypes
import numpy as np

from config import MEDIA_DETECT_THRESHOLD
from debug import debug

VK_MEDIA_PLAY_PAUSE = 0xB3
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002


def _send_media_play_pause():
    """Simulate a press-and-release of the media play/pause key."""
    ctypes.windll.user32.keybd_event(
        VK_MEDIA_PLAY_PAUSE, 0, KEYEVENTF_EXTENDEDKEY, 0
    )
    ctypes.windll.user32.keybd_event(
        VK_MEDIA_PLAY_PAUSE, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0
    )


def pause_media_if_playing(ring_buffer) -> bool:
    """Check the ring buffer for recent audio activity and pause if detected.

    Returns True if media was paused, False otherwise.
    """
    try:
        audio = ring_buffer.read_last(1.0)
        if len(audio) == 0:
            return False

        rms = float(np.sqrt(np.mean(audio ** 2)))
        if rms > MEDIA_DETECT_THRESHOLD:
            debug.log(
                "MediaControl",
                "audio detected — pausing media",
                {"rms": rms},
            )
            _send_media_play_pause()
            return True

        return False
    except (OSError, RuntimeError) as e:
        debug.warn("MediaControl", "failed to check/pause media", e)
        return False


def resume_media():
    """Resume media by sending the play/pause key again."""
    try:
        debug.log("MediaControl", "resuming media playback")
        _send_media_play_pause()
    except (OSError, RuntimeError) as e:
        debug.warn("MediaControl", "failed to resume media", e)
