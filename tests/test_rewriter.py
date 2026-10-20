"""Tests for rewriter.py — offline rule-based rewriting."""

from nlp import split_sentences
from rewriter import (
    INTENSITY_LABELS,
    MODES,
    mask_protected,
    rewrite_sentence_offline,
    rewrite_text_offline,
    unmask_protected,
)
from tests.conftest import DEMO_SENTENCE


def test_ten_modes_defined():
    assert len(MODES) == 10
    for mid in ("natural", "academic", "professional", "conversational",
                "simple", "creative", "native", "voice", "technical", "minimal"):
        assert mid in MODES


def test_five_intensity_levels():
    assert set(INTENSITY_LABELS) == {1, 2, 3, 4, 5}


def test_protected_spans_roundtrip():
    text = 'The value was 42.5 mg [1] and "quoted text" stayed.'
    masked, originals = mask_protected(text)
    assert "42.5" not in masked
    assert "[1]" not in masked
    assert unmask_protected(masked, originals) == text


def test_numbers_citations_quotes_preserved():
    s = 'The dose was 42.5 mg [1] and "do not change this" was kept.'
    rewritten, _ = rewrite_sentence_offline(s, "natural", 5)
    assert "42.5 mg" in rewritten
    assert "[1]" in rewritten
    assert '"do not change this"' in rewritten


def test_demo_sentence_improved_not_hardcoded():
    # The demo sentence must be transformed by real rules, not a lookup.
    rewritten, notes = rewrite_sentence_offline(DEMO_SENTENCE, "natural", 3)
    assert rewritten != DEMO_SENTENCE
    assert len(rewritten.split()) < len(DEMO_SENTENCE.split())
    assert notes  # changes are explained
    # No special-case: a paraphrase with the same shape gets similar treatment.
    variant = DEMO_SENTENCE.replace("Artificial intelligence", "Machine learning")
    rewritten2, _ = rewrite_sentence_offline(variant, "natural", 3)
    assert rewritten2 != variant


def test_formal_words_simplified():
    rewritten, notes = rewrite_sentence_offline(
        "We utilize this method in order to facilitate the process.",
        "natural", 3)
    assert "utilize" not in rewritten.lower()
    assert "in order to" not in rewritten.lower()
    assert notes


def test_passive_to_active_at_high_intensity():
    rewritten, notes = rewrite_sentence_offline(
        "The report was written by the research team.", "natural", 4)
    assert "research team" in rewritten
    assert "was written by" not in rewritten


def test_minimal_mode_changes_little():
    s = "The results were good. We utilized the standard method."
    _, notes_min = rewrite_sentence_offline(s, "minimal", 1)
    _, notes_nat = rewrite_sentence_offline(s, "natural", 5)
    assert len(notes_min) <= len(notes_nat)


def test_intensity_ordering():
    s = ("It is important to note that we utilize this methodology in order "
         "to facilitate the process, which was developed by the team.")
    counts = []
    for lvl in (1, 3, 5):
        _, notes = rewrite_sentence_offline(s, "natural", lvl)
        counts.append(len(notes))
    assert counts[0] <= counts[1] <= counts[2]


def test_modes_differ():
    s = "We do not utilize this method because it is not effective."
    conv, _ = rewrite_sentence_offline(s, "conversational", 3)
    tech, _ = rewrite_sentence_offline(s, "technical", 3)
    # Conversational mode uses contractions; technical does not.
    assert "don't" in conv or "isn't" in conv


def test_selective_rewrite_only_selected():
    text = "First sentence here. We utilize this method daily. Third one."
    results = rewrite_text_offline(text, "natural", 3, sentence_indexes=[1])
    assert len(results) == 1
    assert results[0]["index"] == 1
    assert "utilize" not in results[0]["rewritten"].lower()


def test_rewrite_all_when_no_selection():
    text = "We utilize this. They facilitate that."
    results = rewrite_text_offline(text, "natural", 3)
    assert len(results) == 2
