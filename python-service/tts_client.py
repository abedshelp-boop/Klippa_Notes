"""
TTS hear-back client — speaks confirmations to the user after a capture.

Talks to Sub-project 4's /tts/say endpoint when present. Until that ships,
every call is a no-op (404 swallowed). Built so production code can call
say() unconditionally without conditional branches.

Design notes:
  - GET, not POST: matches the spec's `/tts/say?text=...` shape; the endpoint
    is read-only effectful (synthesize + play locally).
  - 2-second timeout: TTS must feel instant or not happen. A slow TTS path
    is worse than no TTS — it backs up the wake-word lock.
  - Failures are silent and warn-only-once-per-session via a flag, so a
    user without Sub-project 4 doesn't see noise on every capture.
"""
from __future__ import annotations

import http.client
import urllib.parse

from debug import debug

TTS_HOST = "127.0.0.1"
TTS_PORT = 8765
TTS_PATH = "/tts/say"
TIMEOUT_SEC = 2.0

_warned = False


def _http_get(url: str, timeout: float) -> http.client.HTTPResponse:
    """Thin GET wrapper. Split out so tests can mock without going to network."""
    parsed = urllib.parse.urlparse(url)
    conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=timeout)
    conn.request("GET", parsed.path + ("?" + parsed.query if parsed.query else ""))
    return conn.getresponse()


def say(text: str) -> None:
    """Speak `text` via the Python service's TTS endpoint, if available.

    Silently no-ops if the endpoint is missing or unreachable. Never raises."""
    global _warned
    if not text:
        return
    qs = urllib.parse.urlencode({"text": text})
    url = f"http://{TTS_HOST}:{TTS_PORT}{TTS_PATH}?{qs}"
    try:
        resp = _http_get(url, timeout=TIMEOUT_SEC)
        if resp.status == 404 and not _warned:
            debug.log(
                "tts",
                "/tts/say not present (Sub-project 4 not merged) — silencing",
            )
            _warned = True
    except (ConnectionError, TimeoutError, OSError):
        # Network blip or service restart — drop the audible confirmation
        # rather than blocking the save path.
        return
