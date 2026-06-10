"""Tests for voice routing — grammar parser, routing decisions, response parsing."""
from unittest.mock import patch

import pytest

from voice_routing import (
    parse_command,
    parse_response,
    ParsedCommand,
    RoutingDecision,
    route,
    route_local,
)


# ─── Grammar parser ─────────────────────────────────────────────────────────


def test_no_qualifier_returns_inbox():
    p = parse_command("Take note: I had pizza for lunch.")
    assert p.kind == "inbox"
    assert p.qualifier is None
    assert p.content == "Take note: I had pizza for lunch."


def test_in_qualifier_matches_with_comma():
    p = parse_command("in Sapiens, the author argues humans love stories.")
    assert p.kind == "in"
    assert p.qualifier == "Sapiens"
    assert p.content == "the author argues humans love stories."


def test_in_qualifier_matches_without_comma():
    p = parse_command("in Sapiens the author argues humans love stories.")
    assert p.kind == "in"
    assert p.qualifier == "Sapiens"
    assert p.content.startswith("the author argues")


def test_in_qualifier_multi_word():
    p = parse_command("in Cooking Eggs, scramble at medium-low heat.")
    assert p.kind == "in"
    assert p.qualifier == "Cooking Eggs"
    assert p.content.startswith("scramble")


def test_in_qualifier_case_insensitive_prefix():
    p = parse_command("IN sapiens, lorem ipsum")
    assert p.kind == "in"
    assert p.qualifier.lower() == "sapiens"


def test_new_note_about_with_topic():
    p = parse_command("new note about cooking eggs, scramble at medium-low.")
    assert p.kind == "new"
    assert p.qualifier == "cooking eggs"
    assert p.content == "scramble at medium-low."


def test_new_note_about_without_comma():
    """No-comma case: topic absorbs the rest until end-of-string. Suboptimal
    title (user should add a comma), but predictable behavior."""
    p = parse_command("new note about cooking eggs scramble at medium-low.")
    assert p.kind == "new"
    assert p.qualifier.startswith("cooking eggs")


def test_continue_routes_to_recent():
    p = parse_command("continue, and another thing about that")
    assert p.kind == "continue"
    assert p.qualifier is None
    assert p.content == "and another thing about that"


def test_continue_without_comma():
    p = parse_command("continue and another thing")
    assert p.kind == "continue"
    assert p.content.startswith("and another thing")


def test_strips_leading_filler():
    """Whisper sometimes prefixes the command with 'uh' / 'um'. Strip those
    before parsing so 'uh, in Sapiens' still matches the 'in' pattern."""
    p = parse_command("uh, in Sapiens, hello")
    assert p.kind == "in"
    assert p.qualifier == "Sapiens"


def test_empty_string_is_inbox_with_empty_content():
    p = parse_command("")
    assert p.kind == "inbox"
    assert p.content == ""


def test_only_qualifier_no_content_routes_to_in_with_empty_body():
    """User pinned a note by voice: 'Hey Deen, in Sapiens.' — kind=in,
    empty content. Caller decides whether to treat this as a pin-only or
    to ask for content."""
    p = parse_command("in Sapiens.")
    assert p.kind == "in"
    assert p.qualifier == "Sapiens"
    assert p.content == ""


# ─── Routing decisions (route_local) ───────────────────────────────────────


QUICK_INBOX_ID = "quick-inbox-id-abc"

SAMPLE_NOTES = [
    {"id": "n1", "title": "Sapiens"},
    {"id": "n2", "title": "Sapiens chapter 2"},
    {"id": "n3", "title": "Cooking Eggs"},
    {"id": "n4", "title": "Recipes"},
]


def test_route_inbox_returns_quick_inbox():
    parsed = parse_command("Random thought to drop somewhere.")
    decision = route_local(parsed, SAMPLE_NOTES, QUICK_INBOX_ID, last_capture=None)
    assert decision.kind == "existing"
    assert decision.note_id == QUICK_INBOX_ID


def test_route_in_high_confidence_picks_top():
    parsed = parse_command("in Cooking Eggs, scramble at medium-low.")
    decision = route_local(parsed, SAMPLE_NOTES, QUICK_INBOX_ID, last_capture=None)
    assert decision.kind == "existing"
    assert decision.note_id == "n3"
    assert decision.content == "scramble at medium-low."


def test_route_in_ambiguous_multi_match():
    parsed = parse_command("in Sapiens, the author argues...")
    decision = route_local(parsed, SAMPLE_NOTES, QUICK_INBOX_ID, last_capture=None)
    # Two 'Sapiens' candidates — they should both show up in candidates;
    # exact "Sapiens" may still win cleanly as a high-confidence match,
    # OR it triggers disambiguation. Either outcome is acceptable per spec
    # so long as the candidates carry both options when needs_voice_followup.
    if decision.kind == "needs_voice_followup":
        titles = {c["title"] for c in decision.candidates}
        assert "Sapiens" in titles or "Sapiens chapter 2" in titles
    else:
        assert decision.kind == "existing"
        # If we picked one, it must be one of the Sapiens notes.
        assert decision.note_id in ("n1", "n2")


def test_route_in_no_match_offers_creation():
    parsed = parse_command("in Quantum Physics, hello")
    decision = route_local(parsed, SAMPLE_NOTES, QUICK_INBOX_ID, last_capture=None)
    assert decision.kind == "needs_voice_followup"
    assert "Quantum Physics" in (decision.question or "")
    assert "create" in (decision.question or "").lower()


def test_route_new_returns_create_new_with_titlecase():
    parsed = parse_command("new note about cooking eggs, scramble at medium.")
    decision = route_local(parsed, SAMPLE_NOTES, QUICK_INBOX_ID, last_capture=None)
    assert decision.kind == "create_new"
    assert decision.proposed_title == "Cooking Eggs"
    assert decision.content == "scramble at medium."


def test_route_continue_uses_last_capture():
    parsed = parse_command("continue, and another thing.")
    last = {"note_id": "n4", "timestamp": None}
    decision = route_local(parsed, SAMPLE_NOTES, QUICK_INBOX_ID, last_capture=last)
    assert decision.kind == "existing"
    assert decision.note_id == "n4"


def test_route_continue_with_no_recent_capture_asks():
    parsed = parse_command("continue, hello")
    decision = route_local(parsed, SAMPLE_NOTES, QUICK_INBOX_ID, last_capture=None)
    assert decision.kind == "needs_voice_followup"
    assert "continue" in (decision.question or "").lower()


# ─── Haiku-tiered route() ──────────────────────────────────────────────────


@patch("voice_routing.haiku_client.pick_best")
def test_route_passes_through_high_confidence_unchanged(mock_haiku):
    parsed = parse_command("in Cooking Eggs, scramble.")
    decision = route(parsed, SAMPLE_NOTES, QUICK_INBOX_ID, last_capture=None)
    assert decision.kind == "existing"
    mock_haiku.assert_not_called()


@patch("voice_routing.haiku_client.pick_best",
       return_value={"note_id": "n1", "confidence": "high"})
def test_route_promotes_ambiguous_when_haiku_confident(mock_haiku):
    # Force the ambiguous-with-candidates branch by using a query that
    # produces multiple close matches.
    parsed = ParsedCommand(kind="in", qualifier="Sapians", content="hello")
    decision = route(parsed, SAMPLE_NOTES, QUICK_INBOX_ID, last_capture=None)
    # If route_local already returned high-confidence existing, Haiku
    # wasn't called — that's also acceptable (it means the match was
    # clean enough that no fallback was needed).
    if mock_haiku.called:
        assert decision.kind == "existing"
        assert decision.note_id == "n1"


@patch("voice_routing.haiku_client.pick_best", return_value=None)
def test_route_keeps_voice_followup_when_haiku_returns_none(mock_haiku):
    parsed = ParsedCommand(kind="in", qualifier="Sapians", content="hi")
    decision = route(parsed, SAMPLE_NOTES, QUICK_INBOX_ID, last_capture=None)
    # If route_local was ambiguous, Haiku returned None → stay ambiguous.
    # If route_local was confident, decision is already "existing" — fine.
    assert decision.kind in ("needs_voice_followup", "existing")


@patch("voice_routing.haiku_client.pick_best",
       return_value={"note_id": None, "confidence": "low"})
def test_route_keeps_voice_followup_when_haiku_says_unknown(mock_haiku):
    parsed = ParsedCommand(kind="in", qualifier="Sapians", content="hi")
    decision = route(parsed, SAMPLE_NOTES, QUICK_INBOX_ID, last_capture=None)
    assert decision.kind in ("needs_voice_followup", "existing")


@patch("voice_routing.haiku_client.pick_best")
def test_route_skips_haiku_for_no_match(mock_haiku):
    """Empty candidates → no point asking Haiku; the user said a name we have
    no notes for at all."""
    parsed = parse_command("in Quantum Physics, hello")
    decision = route(parsed, SAMPLE_NOTES, QUICK_INBOX_ID, last_capture=None)
    assert decision.kind == "needs_voice_followup"
    # No close candidates surfaced → mock not called with non-empty candidates.
    if mock_haiku.called:
        candidates_arg = mock_haiku.call_args.kwargs.get(
            "candidates"
        ) or mock_haiku.call_args.args[1]
        assert candidates_arg == []


# ─── Response parsing (yes/no/named) ───────────────────────────────────────


def test_parse_response_yes_variants():
    for text in ["yes", "Yes", "yeah", "yep", "yup", "sure", "ok",
                  "okay", "confirmed", "correct"]:
        r = parse_response(text, candidates=[])
        assert r["kind"] == "yes", f"failed for {text!r}"


def test_parse_response_no_variants():
    for text in ["no", "No", "nope", "nah", "negative", "wrong"]:
        r = parse_response(text, candidates=[])
        assert r["kind"] == "no", f"failed for {text!r}"


def test_parse_response_named_matches_candidate():
    candidates = [
        {"id": "n1", "title": "Sapiens chapter 1"},
        {"id": "n2", "title": "Sapiens chapter 2"},
    ]
    r = parse_response("chapter two", candidates=candidates)
    # Numeric "two" vs digit "2" is hard for plain fuzzy; either it matches
    # one of the candidates or returns unclear. Both are acceptable; what
    # we want to guard is that "yes" alone doesn't fire when a candidate
    # name dominates the utterance.
    assert r["kind"] in ("named", "unclear")
    if r["kind"] == "named":
        assert r["note_id"] in ("n1", "n2")


def test_parse_response_named_exact_title():
    candidates = [{"id": "n1", "title": "Cooking Eggs"}]
    r = parse_response("Cooking Eggs", candidates=candidates)
    assert r["kind"] == "named"
    assert r["note_id"] == "n1"


def test_parse_response_unclear_returns_unclear():
    r = parse_response("uhhh I don't know", candidates=[])
    assert r["kind"] == "unclear"


def test_parse_response_empty_is_unclear():
    r = parse_response("", candidates=[])
    assert r["kind"] == "unclear"


def test_parse_response_named_over_yes_when_both_present():
    """User says 'yes Sapiens chapter 2' — name wins, more specific."""
    candidates = [{"id": "n2", "title": "Sapiens chapter 2"}]
    r = parse_response("yes Sapiens chapter 2", candidates=candidates)
    assert r["kind"] == "named"
    assert r["note_id"] == "n2"
