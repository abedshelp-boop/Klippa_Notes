"""
Voice routing — parses the user's command transcript into a structured
destination decision.

Grammar (after "Hey Deen" wake word is stripped by the wake-word detector;
this module sees only the command transcript):

  [content]                              → kind=inbox, content=...
  in <name>[,] [content]                 → kind=in, qualifier=<name>, content=...
  new note about <topic>[,] [content]    → kind=new, qualifier=<topic>, content=...
  continue[,] [content]                  → kind=continue, content=...

Parsing is deliberately conservative: anything that doesn't match one of the
qualifier prefixes falls through to inbox. The matcher (title_matcher) handles
mishearings of the qualifier name itself; Haiku 4.5 picks tie-breakers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Literal, Optional

import haiku_client
import title_matcher


Kind = Literal["inbox", "in", "new", "continue"]


@dataclass(frozen=True)
class ParsedCommand:
    kind: Kind
    qualifier: Optional[str]
    content: str


# Whisper preamble fillers — strip before parsing so 'uh, in Sapiens' parses
# as 'in Sapiens'. Anchored at the start. Inline (?i:...) flag rather than
# the re.IGNORECASE module flag so the case-sensitive content-boundary
# heuristics below stay case-sensitive.
_LEADING_FILLER_RE = re.compile(
    r"^(?i:uh|um|er|so|ok|okay|hey|hey deen|deen)[\s,.\-]+",
)

# Match patterns in priority order: 'new note about' before 'in' (so "in"
# inside a longer "new note about" doesn't shortcut).
# The case-insensitive flag is scoped to the PREFIX only — the qualifier-end
# heuristics ([A-Z] / [a-z]{4,}) below stay case-sensitive, which they MUST
# to do their job.
# Terminator alternatives shared by NEW + IN:
#   [,.](?:\s+|$)        — comma/period followed by whitespace OR end-of-string
#   \s+(?=[a-z]{3,}\s)   — 3+ lowercase letters following a space (sentence-y
#                          word like "scramble" / "argues" / "the author")
#   $                    — bare end-of-string
# 'new note about <topic>' — the topic ends at the first comma/period or
# end-of-string. NO lowercase-word boundary heuristic here: most users say
# multi-word topics ("cooking eggs", "Friday standup"), and the heuristic
# would clip valid topic words. If the user forgets the comma, the topic
# becomes the whole rest of the utterance — annoying but predictable.
_NEW_RE = re.compile(
    r"^(?i:new\s+note\s+about)\s+([A-Za-z][A-Za-z0-9'\- ]*?)"
    r"(?:[,.](?:\s+|$)|$)",
)
_IN_RE = re.compile(
    r"^(?i:in)\s+([A-Za-z][A-Za-z0-9'\- ]*?)"
    r"(?:[,.](?:\s+|$)|\s+(?=[a-z]{3,}\s)|$)",
)
_CONTINUE_RE = re.compile(
    r"^(?i:continue)(?:[,.]\s+|\s+|$)",
)


def parse_command(text: str) -> ParsedCommand:
    """Parse a command transcript into a ParsedCommand.

    Robustness rules:
      - Leading filler ("uh", "um", "so") is stripped.
      - Case-insensitive matching at the prefix.
      - Comma after the qualifier is optional (Whisper sometimes drops it).
      - The qualifier ends at the first comma/period, OR a capitalized word
        boundary (heuristic for "in Sapiens The author..."), OR end of string.
      - Empty / unparseable input → kind=inbox with whatever's left.
    """
    if not text:
        return ParsedCommand(kind="inbox", qualifier=None, content="")

    stripped = text.strip()
    stripped = _LEADING_FILLER_RE.sub("", stripped).strip()

    # ── continue ──
    m = _CONTINUE_RE.match(stripped)
    if m:
        rest = stripped[m.end():].strip()
        return ParsedCommand(kind="continue", qualifier=None, content=rest)

    # ── new note about <topic> ──
    m = _NEW_RE.match(stripped)
    if m:
        qualifier = m.group(1).strip().rstrip(",.")
        rest = stripped[m.end():].strip()
        return ParsedCommand(kind="new", qualifier=qualifier, content=rest)

    # ── in <name> ──
    m = _IN_RE.match(stripped)
    if m:
        qualifier = m.group(1).strip().rstrip(",.")
        rest = stripped[m.end():].strip()
        return ParsedCommand(kind="in", qualifier=qualifier, content=rest)

    # ── fallthrough: inbox ──
    return ParsedCommand(kind="inbox", qualifier=None, content=stripped)


# ─── Routing decision ──────────────────────────────────────────────────────

# Decision-tier thresholds. These are tuned for short titles + voice
# transcription noise; revisit if Abed reports too-many false positives or
# too-many disambiguation prompts in real use.
HIGH_CONFIDENCE_MIN = 0.85
HIGH_CONFIDENCE_GAP = 0.15
CONFIRM_MIN = 0.70
DISAMBIGUATE_MIN = 0.50


@dataclass(frozen=True)
class RoutingDecision:
    """The outcome of routing a parsed command against current notes + state.

    kind:
      - "existing"               → save to note_id (Quick Inbox, pinned, or matched)
      - "create_new"             → caller creates a note with proposed_title
      - "needs_voice_followup"   → caller speaks `question` and listens; handles
                                   yes/no/named answer via parse_response()
    """
    kind: str
    content: str
    note_id: Optional[str] = None
    proposed_title: Optional[str] = None
    candidates: List[dict] = field(default_factory=list)
    question: Optional[str] = None
    confidence: str = "high"


def _titlecase_topic(topic: str) -> str:
    """Convert 'cooking eggs' → 'Cooking Eggs' for new-note titles."""
    return " ".join(w.capitalize() for w in topic.split())


def route_local(
    parsed: ParsedCommand,
    notes: list[dict],
    quick_inbox_id: str,
    last_capture: Optional[dict],
) -> RoutingDecision:
    """Local-only routing: parser + title matcher, no Haiku.

    Caller is responsible for filtering Quick Inbox OUT of the `notes` list
    when scoring 'in <name>' — we don't want fuzzy-matching the inbox itself.
    Quick Inbox enters as the explicit no-qualifier destination only.
    """
    # ── inbox ──
    if parsed.kind == "inbox":
        return RoutingDecision(
            kind="existing",
            note_id=quick_inbox_id,
            content=parsed.content,
            confidence="high",
        )

    # ── continue ──
    if parsed.kind == "continue":
        if last_capture and last_capture.get("note_id"):
            return RoutingDecision(
                kind="existing",
                note_id=last_capture["note_id"],
                content=parsed.content,
                confidence="high",
            )
        return RoutingDecision(
            kind="needs_voice_followup",
            content=parsed.content,
            question=(
                "Nothing to continue — you haven't captured recently. "
                "Name a note, or say inbox."
            ),
            candidates=[],
            confidence="low",
        )

    # ── new ──
    if parsed.kind == "new":
        title = _titlecase_topic(parsed.qualifier or "Untitled")
        return RoutingDecision(
            kind="create_new",
            proposed_title=title,
            content=parsed.content,
            confidence="high",
        )

    # ── in <name> ──  (only remaining kind)
    if not parsed.qualifier:
        return RoutingDecision(
            kind="existing",
            note_id=quick_inbox_id,
            content=parsed.content,
            confidence="low",
        )

    candidates_pool = [n for n in notes if n.get("id") != quick_inbox_id]
    if not candidates_pool:
        return RoutingDecision(
            kind="needs_voice_followup",
            content=parsed.content,
            question=(
                f"No note called {parsed.qualifier}. "
                "Create one? Say yes or no."
            ),
            candidates=[],
            confidence="low",
        )

    ranked = title_matcher.score_all(parsed.qualifier, candidates_pool)
    if not ranked:
        return RoutingDecision(
            kind="needs_voice_followup",
            content=parsed.content,
            question=f"No notes to match {parsed.qualifier}. Say a note name.",
            confidence="low",
        )

    top = ranked[0]
    second_score = ranked[1].combined_score if len(ranked) > 1 else 0.0
    gap = top.combined_score - second_score

    # High confidence: clear winner.
    if top.combined_score >= HIGH_CONFIDENCE_MIN and gap >= HIGH_CONFIDENCE_GAP:
        return RoutingDecision(
            kind="existing",
            note_id=top.note_id,
            content=parsed.content,
            confidence="high",
        )

    # Mid confidence, no clear second: ask to confirm.
    if top.combined_score >= CONFIRM_MIN and gap >= HIGH_CONFIDENCE_GAP:
        return RoutingDecision(
            kind="needs_voice_followup",
            content=parsed.content,
            candidates=[{"id": top.note_id, "title": top.title,
                          "score": top.combined_score}],
            question=f"Did you mean {top.title}? Say yes or no.",
            confidence="medium",
        )

    # Two or more close candidates: ask which.
    close_candidates = [
        r for r in ranked
        if r.combined_score >= DISAMBIGUATE_MIN
        and (top.combined_score - r.combined_score) < HIGH_CONFIDENCE_GAP
    ]
    if len(close_candidates) >= 2:
        names = " or ".join(c.title for c in close_candidates[:3])
        return RoutingDecision(
            kind="needs_voice_followup",
            content=parsed.content,
            candidates=[
                {"id": c.note_id, "title": c.title, "score": c.combined_score}
                for c in close_candidates[:5]
            ],
            question=f"{names}? Say which.",
            confidence="medium",
        )

    # Single mid-low score, no close runner-up: confirm anyway.
    if top.combined_score >= DISAMBIGUATE_MIN:
        return RoutingDecision(
            kind="needs_voice_followup",
            content=parsed.content,
            candidates=[{"id": top.note_id, "title": top.title,
                          "score": top.combined_score}],
            question=f"Did you mean {top.title}? Say yes or no.",
            confidence="medium",
        )

    # No match at all.
    return RoutingDecision(
        kind="needs_voice_followup",
        content=parsed.content,
        question=(
            f"No note called {parsed.qualifier}. "
            "Create one? Say yes or no."
        ),
        confidence="low",
    )


def route(
    parsed: ParsedCommand,
    notes: list[dict],
    quick_inbox_id: str,
    last_capture: Optional[dict],
) -> RoutingDecision:
    """Full routing: local tier first, Haiku fallback for ambiguous results
    with at least one candidate.

    The Haiku fallback ONLY runs for `needs_voice_followup` with candidates,
    not for empty/no-match cases (no point asking Haiku to pick from nothing).
    """
    decision = route_local(parsed, notes, quick_inbox_id, last_capture)

    if decision.kind != "needs_voice_followup" or not decision.candidates:
        return decision

    haiku_result = haiku_client.pick_best(
        query=parsed.qualifier or "",
        candidates=decision.candidates,
        content=decision.content,
    )
    if not haiku_result:
        return decision
    if haiku_result.get("confidence") != "high":
        return decision
    note_id = haiku_result.get("note_id")
    if not note_id:
        return decision
    return RoutingDecision(
        kind="existing",
        note_id=note_id,
        content=decision.content,
        confidence="high",
    )


# ─── Response parsing (disambiguation loop) ────────────────────────────────

_YES_WORDS = {
    "yes", "yeah", "yep", "yup", "ok", "okay", "sure", "confirmed",
    "correct", "affirmative", "right",
}
_NO_WORDS = {
    "no", "nope", "nah", "negative", "wrong", "incorrect",
}


def parse_response(text: str, candidates: list[dict]) -> dict:
    """Parse a yes/no/named answer from a spoken disambiguation reply.

    Returns one of:
      {"kind": "yes"}
      {"kind": "no"}
      {"kind": "named", "note_id": "...", "title": "..."}
      {"kind": "unclear"}

    Named match wins over yes — if the user says "yes Sapiens chapter 2",
    they're naming a candidate, not just confirming. The candidate list is
    typically 1-3 items deep, so we fuzzy-match against each.
    """
    if not text or not text.strip():
        return {"kind": "unclear"}

    cleaned = text.strip().lower().rstrip(".!?")

    # Try named match first — fuzzy against each candidate title.
    if candidates:
        best = None
        best_score = 0.0
        for c in candidates:
            score = title_matcher._fuzzy_score(cleaned, (c.get("title") or "").lower())
            if score > best_score:
                best_score = score
                best = c
        if best and best_score >= 0.55:
            return {
                "kind": "named",
                "note_id": best["id"],
                "title": best.get("title") or "",
            }

    # Yes / no detection — match individual words or short phrases.
    tokens = set(cleaned.replace(",", " ").split())
    if tokens & _YES_WORDS or cleaned in _YES_WORDS:
        return {"kind": "yes"}
    if tokens & _NO_WORDS or cleaned in _NO_WORDS:
        return {"kind": "no"}

    return {"kind": "unclear"}
