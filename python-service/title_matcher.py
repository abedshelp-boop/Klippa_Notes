"""
Title matcher — ranks notes by similarity to a spoken qualifier.

Two scorers combine into one decision:
  - rapidfuzz token_set_ratio: fast, string-distance, catches mishearings
    ('Sapians' → 'Sapiens').
  - sentence-transformers cosine: semantic, catches paraphrases ('cooking
    notes' → 'Recipes'). OPTIONAL — if sentence-transformers isn't installed
    or fails to load, we silently fall back to rapidfuzz-only. The voice
    routing tier handles low-confidence outcomes by escalating to Haiku.

The combined score is a weighted average (rapidfuzz 0.6, embedding 0.4) so
exact-ish string matches dominate but semantic matches still surface.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from rapidfuzz import fuzz

from debug import debug


@dataclass(frozen=True)
class MatchResult:
    note_id: str
    title: str
    fuzzy_score: float       # 0..1
    embedding_score: float   # 0..1, or 0.0 if embedding unavailable
    combined_score: float    # 0..1


# Lazy module-level state for the embedding model. Loading torch + a 80MB
# model takes 2-5 seconds the first time, so we defer until first use.
_embedding_model = None
_embedding_load_attempted = False


def _get_embedding_model():
    """Lazy-load the sentence-transformers model. Returns None if unavailable
    (no install, no network, no disk — any of which we tolerate)."""
    global _embedding_model, _embedding_load_attempted
    if _embedding_load_attempted:
        return _embedding_model
    _embedding_load_attempted = True
    try:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2"
        )
        debug.log("matcher", "embedding model loaded")
    except (ImportError, OSError, RuntimeError) as e:
        debug.warn(
            "matcher",
            "embedding model unavailable — using rapidfuzz only",
            str(e),
        )
        _embedding_model = None
    return _embedding_model


def _fuzzy_score(query: str, title: str) -> float:
    """token_set_ratio handles word reordering and stop-word noise better than
    plain ratio, which matters for spoken titles like 'Cooking Eggs' vs.
    'eggs cooking'."""
    if not query or not title:
        return 0.0
    return fuzz.token_set_ratio(query, title) / 100.0


def _embedding_scores(query: str, titles: list[str]) -> list[float]:
    """Cosine-similarity scores for one query against many titles. Returns
    a list of 0..1 floats (negative similarities are clamped to 0)."""
    if not query or not titles:
        return [0.0] * len(titles)
    model = _get_embedding_model()
    if model is None:
        return [0.0] * len(titles)
    try:
        all_texts = [query] + titles
        embeddings = model.encode(all_texts, normalize_embeddings=True)
        query_vec = embeddings[0]
        title_vecs = embeddings[1:]
        sims = (title_vecs @ query_vec).tolist()
        return [max(0.0, min(1.0, float(s))) for s in sims]
    except (RuntimeError, ValueError) as e:
        debug.warn("matcher", "embedding scoring failed", str(e))
        return [0.0] * len(titles)


def score_all(
    query: str,
    notes: Iterable[dict],
    fuzzy_weight: float = 0.6,
    embedding_weight: float = 0.4,
) -> list[MatchResult]:
    """Score every note's title against the query. Returns results sorted by
    combined_score descending."""
    notes_list = list(notes)
    if not notes_list:
        return []

    titles = [n.get("title") or "" for n in notes_list]
    emb_scores = _embedding_scores(query, titles)
    embedding_available = _get_embedding_model() is not None

    results = []
    for note, emb_score in zip(notes_list, emb_scores):
        title = note.get("title") or ""
        fuzzy = _fuzzy_score(query, title)
        if not embedding_available:
            combined = fuzzy
        else:
            combined = fuzzy * fuzzy_weight + emb_score * embedding_weight
        results.append(MatchResult(
            note_id=note["id"],
            title=title,
            fuzzy_score=fuzzy,
            embedding_score=emb_score,
            combined_score=combined,
        ))

    results.sort(key=lambda r: r.combined_score, reverse=True)
    return results
