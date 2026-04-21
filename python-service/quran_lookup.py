"""
Quran enrichment: detect Quranic recitation in a transcript and replace it
with the canonical Uthmani text looked up from a bundled corpus.

Why: Whisper transcribes recitation phonetically and introduces errors; the
LLM then reconstructs Arabic script on top of those errors, producing text
that looks Quranic but has wrong letters/words (theologically unacceptable).
This module short-circuits that by fuzzy-matching the Whisper output against
the full Quran corpus and replacing matched passages with byte-exact canonical
text. Text that doesn't confidently match stays unchanged — we don't overwrite
hadith, du'a, or general Arabic speech.

Public:
    enrich_quran_in_transcript(s) -> s    # one-call entry point
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from rapidfuzz import fuzz, process

_CORPUS_PATH = Path(__file__).parent / "data" / "quran_uthmani.json"

# ─── Normalization ───────────────────────────────────────────────────────────

# Arabic tashkil (diacritics) + tatweel + small Quranic marks. Stripped during
# comparison so that Whisper output (which has inconsistent/missing diacritics)
# can still match the fully-vocalized Uthmani corpus.
_DIACRITICS_RE = re.compile(r"[\u064B-\u065F\u0670\u0640\u06D6-\u06ED]")
# Keep only Arabic letters + whitespace for comparison.
_NON_ARABIC_RE = re.compile(r"[^\u0621-\u063A\u0641-\u064A\u0671-\u06D3\s]")
# A single Arabic "word" — used to tokenize transcripts into an Arabic-only
# word stream (preserving each token's original character position) so that
# punctuation, English interludes, and whitespace between ayahs don't break
# multi-ayah matching.
_ARABIC_WORD_RE = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F][\u0600-\u06FF\u0750-\u077F\u064B-\u065F\u0670]*"
)


def _normalize(s: str) -> str:
    """Strip tashkil and unify letter-shape variants so noisy Whisper output
    lines up with canonical Uthmani text for fuzzy comparison."""
    s = _DIACRITICS_RE.sub("", s)
    # Unify hamza-bearing alif and bare alif variants (ٱ إ أ آ → ا).
    s = re.sub(r"[إأآٱ]", "ا", s)
    # Unify ya variants (ى → ي) and ta-marbuta → ha (handles ة vs ه confusion).
    s = s.replace("ى", "ي").replace("ة", "ه")
    # Hamza-on-seat letters normalize to their base.
    s = s.replace("ؤ", "و").replace("ئ", "ي").replace("ء", "")
    s = _NON_ARABIC_RE.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ─── Corpus ──────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _corpus() -> dict:
    data = json.loads(_CORPUS_PATH.read_text(encoding="utf-8"))
    verses = data["verses"]
    normalized = [_normalize(v["t"]) for v in verses]
    norm_word_counts = [len(n.split()) for n in normalized]
    by_ref: dict[tuple[int, int], int] = {
        (v["s"], v["a"]): i for i, v in enumerate(verses)
    }
    return {
        "verses": verses,
        "surahs": data["surahs"],
        "normalized": normalized,
        "norm_word_counts": norm_word_counts,
        "by_ref": by_ref,
    }


# ─── Matching ────────────────────────────────────────────────────────────────

# Score thresholds (0-100). Partial_ratio is used for the initial probe so a
# transcript prefix can match even when Whisper drops/adds a word or two.
_FIND_THRESHOLD = 78
_EXTEND_THRESHOLD = 72
# Too-short windows are rejected — 3-4 common Arabic words ("and that is")
# can fuzzy-match a Quran verse by coincidence.
_MIN_PROBE_WORDS = 4


def _match_count_for_ayah(
    norm_words: list[str], start_idx: int, ayah_idx: int
) -> tuple[int, int]:
    """Try several slab sizes around the target ayah length; return the
    (words_consumed, score) of the best-fitting slab. Lets Whisper drop or
    duplicate a word or two without breaking alignment to the next ayah.

    Also handles partial recitations: if the transcript is shorter than the
    target ayah (reciter stopped mid-ayah, or the buffer cut off), fall back
    to partial_ratio over whatever remains. partial_ratio finds the best
    substring alignment, so a 19-word transcript of a 50-word ayah can
    still score high if those 19 words match a contiguous portion."""
    c = _corpus()
    ayah_norm = c["normalized"][ayah_idx]
    if not ayah_norm:
        return (0, 0)
    target = c["norm_word_counts"][ayah_idx]
    available = len(norm_words) - start_idx

    best_score = 0
    best_consumed = 0
    for delta in range(-3, 4):
        size = target + delta
        end = start_idx + size
        if size < 1 or end > len(norm_words) or end <= start_idx:
            continue
        slab = " ".join(norm_words[start_idx:end])
        score = fuzz.ratio(slab, ayah_norm)
        if score > best_score:
            best_score = score
            best_consumed = size

    # Partial-ayah fallback: transcript ends mid-ayah with fewer words than
    # the canonical. A recitation cut short still deserves a correct match.
    if best_score < _FIND_THRESHOLD and 0 < available < target:
        slab = " ".join(norm_words[start_idx:])
        pscore = fuzz.partial_ratio(slab, ayah_norm)
        if pscore > best_score:
            best_score = int(pscore)
            best_consumed = available

    return (best_consumed, int(best_score))


def _find_starting_ayah(norm_words: list[str]) -> tuple[int, int] | None:
    """Find the corpus ayah whose prefix best matches the first words of
    `norm_words`. Returns (corpus_idx, score) or None."""
    if len(norm_words) < _MIN_PROBE_WORDS:
        return None
    c = _corpus()
    # Probe with the first 15 words — long enough to uniquely identify an ayah,
    # short enough to stay fast against the 6,236-ayah corpus.
    probe = " ".join(norm_words[:15])
    result = process.extractOne(
        probe,
        c["normalized"],
        scorer=fuzz.partial_ratio,
        score_cutoff=_FIND_THRESHOLD,
    )
    if result is None:
        return None
    return (result[2], int(result[1]))


def _find_passage(norm_words: list[str]) -> dict | None:
    """Find one contiguous Quranic passage beginning at norm_words[0].

    Returns None if no confident start-match; otherwise a dict with surah,
    ayah_start, ayah_end, words_consumed, canonical (joined Uthmani text),
    and the surah name."""
    start = _find_starting_ayah(norm_words)
    if start is None:
        return None
    c = _corpus()
    ayah_idx, _probe_score = start
    first = c["verses"][ayah_idx]
    surah = first["s"]
    ayah_start = first["a"]

    consumed, score = _match_count_for_ayah(norm_words, 0, ayah_idx)
    if consumed == 0 or score < _FIND_THRESHOLD:
        return None

    total_consumed = consumed
    ayah_end = ayah_start
    canonical_parts = [first["t"]]

    # Extend greedily to adjacent ayahs in the same surah as long as they
    # keep matching the transcript. Crossing surah boundaries would be odd
    # for recitation and invites false positives, so we stay within one surah.
    surah_entry = c["surahs"].get(str(surah))
    max_ayah = surah_entry["ayat_count"] if surah_entry else 9999

    cursor_ayah = ayah_start + 1
    next_idx = ayah_idx + 1
    while (
        total_consumed < len(norm_words)
        and next_idx < len(c["verses"])
        and cursor_ayah <= max_ayah
    ):
        nxt = c["verses"][next_idx]
        if nxt["s"] != surah or nxt["a"] != cursor_ayah:
            break
        nconsumed, nscore = _match_count_for_ayah(
            norm_words, total_consumed, next_idx
        )
        if nconsumed == 0 or nscore < _EXTEND_THRESHOLD:
            break
        total_consumed += nconsumed
        ayah_end = cursor_ayah
        canonical_parts.append(nxt["t"])
        cursor_ayah += 1
        next_idx += 1

    surah_name = surah_entry["name_translit"] if surah_entry else f"Surah {surah}"
    return {
        "surah": surah,
        "surah_name": surah_name,
        "ayah_start": ayah_start,
        "ayah_end": ayah_end,
        "words_consumed": total_consumed,
        "canonical": " ".join(canonical_parts),
    }


# ─── Public enrichment ───────────────────────────────────────────────────────

def _format_passage(p: dict) -> str:
    """Render a matched passage in the format the note-generation prompt
    already expects for Quran: `<canonical text> (Surah Name, X:Y)` or
    `... X:Y-Z` for multi-ayah passages."""
    if p["ayah_start"] == p["ayah_end"]:
        ref = f"{p['surah']}:{p['ayah_start']}"
    else:
        ref = f"{p['surah']}:{p['ayah_start']}-{p['ayah_end']}"
    return f"<{p['canonical']}> (Surah {p['surah_name']}, {ref})"


def enrich_quran_in_transcript(transcript: str) -> str:
    """Entry point: return the transcript with every confidently-matched
    Quranic passage swapped for its canonical Uthmani form plus a
    `(Surah Name, X:Y-Z)` reference. Non-Arabic text and non-Quranic Arabic
    pass through untouched.

    Safe to call on any transcript — if there's no Arabic content, or no
    confident Quran match, the output is identical to the input."""
    if not transcript:
        return transcript

    # Tokenize the transcript into Arabic words, preserving each token's
    # original character position. Everything outside these tokens
    # (English, punctuation, whitespace, non-Arabic script) passes through
    # verbatim in the final output.
    tokens: list[dict] = []
    for m in _ARABIC_WORD_RE.finditer(transcript):
        norm = _normalize(m.group(0))
        if not norm:
            continue
        tokens.append({"start": m.start(), "end": m.end(), "norm": norm})

    if len(tokens) < _MIN_PROBE_WORDS:
        return transcript

    norm_words = [t["norm"] for t in tokens]

    # Walk the Arabic word stream; every time we find a confident Quranic
    # passage, record which tokens it covers so we can map back to original
    # character positions for replacement.
    passages: list[tuple[int, int, dict]] = []  # (first_tok, last_tok_exclusive, data)
    i = 0
    while i < len(norm_words):
        passage = _find_passage(norm_words[i:])
        if passage is None or passage["words_consumed"] == 0:
            i += 1
            continue
        passages.append((i, i + passage["words_consumed"], passage))
        i += passage["words_consumed"]

    if not passages:
        return transcript

    # Stitch the output: preserve the original transcript outside each matched
    # passage, and splice canonical text in place of the matched token range
    # (which also swallows any punctuation/whitespace between those tokens).
    out: list[str] = []
    cursor = 0
    for first_tok, last_tok, passage in passages:
        span_start = tokens[first_tok]["start"]
        span_end = tokens[last_tok - 1]["end"]
        out.append(transcript[cursor:span_start])
        out.append(_format_passage(passage))
        cursor = span_end
    out.append(transcript[cursor:])
    return "".join(out)
