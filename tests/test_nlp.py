"""Tests for nlp.py heuristics."""

from nlp import (
    count_syllables,
    find_formality,
    find_passives,
    find_transitions,
    flesch_kincaid_grade,
    flesch_reading_ease,
    repeated_trigrams,
    split_paragraphs,
    split_sentences,
    words,
)


def test_split_sentences_basic():
    sents = split_sentences("Hello world. This is a test! Really?")
    assert [s["text"] for s in sents] == ["Hello world.", "This is a test!", "Really?"]


def test_split_sentences_abbreviations():
    sents = split_sentences("Dr. Smith met Mr. Jones in the U.S. They talked.")
    assert len(sents) == 2
    assert sents[0]["text"].startswith("Dr. Smith")


def test_split_sentences_empty():
    assert split_sentences("") == []
    assert split_sentences("   ") == []


def test_split_paragraphs():
    paras = split_paragraphs("First.\n\nSecond.\n\nThird.")
    assert paras == ["First.", "Second.", "Third."]


def test_words():
    assert words("Hello, world!") == ["Hello", "world"]


def test_syllables():
    assert count_syllables("hello") == 2
    assert count_syllables("the") == 1
    assert count_syllables("reading") == 2
    assert count_syllables("beautiful") == 3
    assert count_syllables("a") == 1


def test_flesch_known_values():
    # "The cat sat on the mat." -> 6 words, 1 sentence, 6 syllables.
    ease = flesch_reading_ease(6, 1, 6)
    assert ease > 100  # extremely easy
    grade = flesch_kincaid_grade(6, 1, 6)
    assert grade < 2


def test_find_passives():
    hits = find_passives("The report was written by the team.")
    assert len(hits) == 1
    assert hits[0]["participle"].lower() == "written"
    assert find_passives("The team wrote the report.") == []


def test_find_transitions():
    hits = find_transitions("Furthermore, it is important to note that this works.")
    phrases = {h["phrase"] for h in hits}
    assert "furthermore" in phrases
    assert "it is important to note that" in phrases


def test_find_formality():
    hits = find_formality("We utilize this method in order to facilitate learning.")
    kinds = {h["kind"] for h in hits}
    assert "word" in kinds  # utilize, facilitate
    assert "phrase" in kinds  # in order to
    by_match = {h["match"].lower(): h["suggestion"] for h in hits}
    assert by_match["utilize"] == "use"
    assert by_match["in order to"] == "to"


def test_repeated_trigrams():
    sents = ["The cat sat down.", "The cat sat still.", "Dogs bark loudly."]
    reps = repeated_trigrams(sents)
    assert any(r["phrase"] == "the cat sat" for r in reps)
