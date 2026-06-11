"""
Anthropic Claude Haiku 4.5 — fallback tie-breaker for voice routing.

Local matcher (rapidfuzz + embeddings) handles 95% of voice routing
unambiguously. When local can't decide — multiple close candidates, or a
borderline mishearing — this client asks Haiku to pick.

Design:
  - Cheap (~$0.0001/call), fast (~300ms p50).
  - Graceful skip: missing key, network down, malformed response → return
    None. The caller (voice_routing.route) treats None as "fall through to
    disambiguation loop", which is the right behavior either way.
  - Structured output via system prompt + JSON-only request. We don't use
    tool-use because the response is one tiny JSON object — over-engineered
    for this case.
"""
from __future__ import annotations

import json
import os
from typing import Optional

from debug import debug

MODEL_ID = "claude-haiku-4-5"
MAX_TOKENS = 80


def _get_api_key() -> Optional[str]:
    """Read the key fresh each call so a settings-runtime update propagates
    without restarting the service."""
    return os.environ.get("ANTHROPIC_API_KEY") or None


_client_cache: dict = {"key": None, "client": None}


def _get_client():
    """Lazy + cached Anthropic client. Rebuilt if the API key rotates."""
    key = _get_api_key()
    if not key:
        return None
    if _client_cache["key"] == key and _client_cache["client"] is not None:
        return _client_cache["client"]
    try:
        from anthropic import Anthropic
    except ImportError:
        debug.warn("haiku", "anthropic SDK not installed — Haiku tier disabled")
        return None
    client = Anthropic(api_key=key)
    _client_cache["key"] = key
    _client_cache["client"] = client
    return client


_SYSTEM_PROMPT = (
    "You disambiguate a spoken note-routing command. Given the user's spoken "
    "qualifier, what they actually want to capture, and a list of candidate "
    "note titles, pick which note they meant.\n\n"
    "Return ONLY valid JSON: {\"note_id\": \"<id from candidates>\", "
    "\"confidence\": \"high\"|\"low\"}. If no candidate matches with "
    "reasonable confidence, return {\"note_id\": null, \"confidence\": \"low\"}.\n\n"
    "No prose. No code fences. JSON only."
)


def pick_best(
    query: str,
    candidates: list[dict],
    content: str,
) -> Optional[dict]:
    """Ask Haiku to pick the best-matching note from `candidates`.

    Returns {"note_id": str | None, "confidence": "high"|"low"} on success,
    None on any failure (no key, network error, parse failure, empty input).
    """
    if not candidates:
        return None
    if not _get_api_key():
        return None

    try:
        client = _get_client()
        if client is None:
            return None

        candidate_lines = "\n".join(
            f"- id={c['id']}: {c.get('title') or ''}" for c in candidates
        )
        user_message = (
            f"Spoken qualifier: {query!r}\n"
            f"Captured content: {content!r}\n"
            f"Candidates:\n{candidate_lines}"
        )

        resp = client.messages.create(
            model=MODEL_ID,
            max_tokens=MAX_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        raw = "".join(
            getattr(block, "text", "") for block in (resp.content or [])
        ).strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = json.loads(raw)

        if not isinstance(parsed, dict):
            return None
        note_id = parsed.get("note_id")
        if note_id is not None and not any(c["id"] == note_id for c in candidates):
            # Hallucinated id — refuse and downgrade.
            return None
        confidence = parsed.get("confidence")
        if confidence not in ("high", "low"):
            confidence = "low"
        return {"note_id": note_id, "confidence": confidence}

    except (json.JSONDecodeError, ValueError, KeyError) as e:
        debug.warn("haiku", "parse failure", str(e))
        return None
    except Exception as e:  # noqa: BLE001 — Anthropic raises various subclasses; degrade for all
        debug.warn("haiku", "API call failed", str(e))
        return None
