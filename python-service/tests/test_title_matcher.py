"""Tests for title_matcher.score_all — rapidfuzz + optional embedding scoring."""
import pytest

from title_matcher import score_all


SAMPLE_NOTES = [
    {"id": "n1", "title": "Sapiens"},
    {"id": "n2", "title": "Sapiens chapter 2"},
    {"id": "n3", "title": "Cooking Eggs"},
    {"id": "n4", "title": "Recipes"},
    {"id": "n5", "title": "Weekly Standup"},
]


def test_exact_match_is_high_confidence():
    results = score_all("Sapiens", SAMPLE_NOTES)
    top = results[0]
    assert top.note_id == "n1"
    assert top.combined_score >= 0.95
    assert top.fuzzy_score >= 0.95


def test_mishearing_still_ranks_correct_note_first():
    """'Sapians' (mis-heard 'Sapiens') should still pick a Sapiens note, not
    something unrelated. May tie between the two Sapiens variants — that's
    fine; we just need a Sapiens-family hit at the top."""
    results = score_all("Sapians", SAMPLE_NOTES)
    assert results[0].note_id in ("n1", "n2")
    assert results[0].combined_score >= 0.60


def test_unrelated_input_low_score():
    results = score_all("Quantum Physics", SAMPLE_NOTES)
    assert results[0].combined_score < 0.60


def test_results_sorted_descending():
    results = score_all("Standup", SAMPLE_NOTES)
    for i in range(len(results) - 1):
        assert results[i].combined_score >= results[i + 1].combined_score


def test_empty_notes_returns_empty():
    assert score_all("anything", []) == []


def test_empty_query_returns_zero_scores():
    results = score_all("", SAMPLE_NOTES)
    assert all(r.combined_score == 0 for r in results)


def test_result_has_both_scores():
    results = score_all("Sapiens", SAMPLE_NOTES)
    top = results[0]
    assert 0.0 <= top.fuzzy_score <= 1.0
    assert 0.0 <= top.embedding_score <= 1.0
    assert 0.0 <= top.combined_score <= 1.0
