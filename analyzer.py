"""Stylistic text analysis for HumanWrite AI v1.

Produces sentence-level flags and document metrics describing writing
*style* (sentence length, passive voice, transition overuse, formality,
repetition). Every result is labelled as a stylistic assessment with
uncertainty — the analyzer NEVER claims to establish authorship and NEVER
fabricates detector scores. See DISCLAIMER.
"""

from __future__ import annotations

import statistics

from nlp import (
    basic_checks,
    count_syllables,
    find_formality,
    find_passives,
    find_transitions,
    flesch_ease_label,
    flesch_kincaid_grade,
    flesch_reading_ease,
    repeated_trigrams,
    sentence_openers,
    split_paragraphs,
    split_sentences,
    words,
)

DISCLAIMER = (
    "Stylistic assessment only. The patterns below describe writing style "
    "(sentence structure, word choice, repetition). They do not establish "
    "whether a human or an AI wrote the text, and no authorship claim is "
    "made or implied. Treat every flag as a suggestion to review, not a verdict."
)


def _strength(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


def analyze_text(text: str) -> dict:
    """Analyze text and return {sentences, metrics, doc_notes, disclaimer}."""
    text = (text or "").strip()
    sentences = split_sentences(text)
    paragraphs = split_paragraphs(text)

    all_words = words(text)
    n_words = len(all_words)
    n_sentences = len(sentences)
    n_syllables = sum(count_syllables(w) for w in all_words)

    sent_texts = [s["text"] for s in sentences]
    lengths = [len(words(s)) for s in sent_texts]
    avg_len = round(statistics.fmean(lengths), 1) if lengths else 0.0
    cv = (statistics.pstdev(lengths) / avg_len) if lengths and avg_len else 0.0

    ease = flesch_reading_ease(n_words, n_sentences, n_syllables)
    grade = flesch_kincaid_grade(n_words, n_sentences, n_syllables)

    # Document-level repetition signals (computed once).
    trigrams = repeated_trigrams(sent_texts)
    openers = sentence_openers(sent_texts)
    repeated_openers = {w: c for w, c in openers.items() if c >= 3 and n_sentences >= 4}

    total_passives = 0
    analyzed = []
    for i, s in enumerate(sentences):
        flags: list[dict] = []
        stext = s["text"]
        wcount = len(words(stext))

        # 1. Sentence length.
        if wcount > 40:
            flags.append({
                "type": "long_sentence",
                "label": "Very long sentence",
                "detail": f"{wcount} words. Very long sentences are harder to "
                          "follow; consider splitting it.",
                "strength": "high",
            })
        elif wcount > 28:
            flags.append({
                "type": "long_sentence",
                "label": "Long sentence",
                "detail": f"{wcount} words. Long sentences can feel heavy; a "
                          "split may improve readability.",
                "strength": "medium",
            })
        elif wcount < 6 and n_sentences > 1:
            flags.append({
                "type": "short_sentence",
                "label": "Very short sentence",
                "detail": "Very short sentences add punch, but several in a "
                          "row can feel choppy.",
                "strength": "low",
            })

        # 2. Passive voice.
        passives = find_passives(stext)
        total_passives += len(passives)
        for p in passives:
            flags.append({
                "type": "passive_voice",
                "label": "Passive construction",
                "detail": f"“{p['phrase']}” is passive. Active voice "
                          "(“X did Y”) is usually more direct.",
                "strength": "medium",
            })

        # 3. Transition phrases.
        for t in find_transitions(stext):
            flags.append({
                "type": "transition",
                "label": "Formulaic transition" if t["weight"] >= 0.6 else "Transition phrase",
                "detail": f"“{t['phrase']}” is a common transitional phrase. "
                          "Occasional use is fine; repeated use across a "
                          "document feels formulaic.",
                "strength": _strength(t["weight"]),
            })

        # 4. Formality / filler.
        for f in find_formality(stext):
            if f["kind"] == "filler":
                flags.append({
                    "type": "filler",
                    "label": "Filler word",
                    "detail": f"“{f['match']}” adds little meaning and can "
                              "usually be removed.",
                    "strength": "low",
                })
            else:
                flags.append({
                    "type": "formality",
                    "label": "Formal / wordy phrasing",
                    "detail": f"“{f['match']}” could be simpler: "
                              f"“{f['suggestion']}”. Plain wording reads as "
                              "more natural.",
                    "strength": "medium",
                })

        # 5. Within-sentence repetition.
        toks = [w.lower() for w in words(stext)]
        dupes = {w for w in set(toks) if toks.count(w) >= 3 and len(w) > 3}
        for d in sorted(dupes)[:2]:
            flags.append({
                "type": "repetition",
                "label": "Repeated word",
                "detail": f"“{d}” appears {toks.count(d)} times in one "
                          "sentence. Varying wording improves flow.",
                "strength": "low",
            })

        analyzed.append({
            "index": i,
            "text": stext,
            "word_count": wcount,
            "flags": flags,
        })

    # Document-level notes.
    doc_notes: list[dict] = []
    if n_sentences >= 4 and cv < 0.25:
        doc_notes.append({
            "type": "uniformity",
            "label": "Uniform sentence length",
            "detail": "Sentences are all about the same length. Varying "
                      "short and long sentences makes writing feel more natural.",
            "strength": "medium",
        })
    if n_sentences and total_passives / n_sentences > 0.4 and total_passives >= 3:
        doc_notes.append({
            "type": "passive_overuse",
            "label": "Frequent passive voice",
            "detail": f"{total_passives} passive constructions in "
                      f"{n_sentences} sentences. Prefer active voice where the "
                      "actor is known.",
            "strength": "medium",
        })
    for tri in trigrams[:5]:
        doc_notes.append({
            "type": "repetition",
            "label": "Repeated phrasing",
            "detail": f"“{tri['phrase']}” appears in {tri['count']} sentences. "
                      "Consider varying the wording.",
            "strength": "medium" if tri["count"] > 2 else "low",
        })
    for opener, count in sorted(repeated_openers.items(), key=lambda x: -x[1])[:3]:
        doc_notes.append({
            "type": "opener_repetition",
            "label": "Repeated sentence opener",
            "detail": f"{count} sentences start with “{opener.capitalize()}”. "
                      "Varying openers improves rhythm.",
            "strength": "low",
        })
    for b in basic_checks(text):
        doc_notes.append({
            "type": b["type"],
            "label": "Mechanical issue",
            "detail": b["detail"],
            "strength": "low",
        })

    total_flags = sum(len(s["flags"]) for s in analyzed)
    metrics = {
        "word_count": n_words,
        "sentence_count": n_sentences,
        "paragraph_count": len(paragraphs),
        "avg_sentence_length": avg_len,
        "sentence_length_variation": round(cv, 2),
        "flesch_reading_ease": ease,
        "flesch_ease_label": flesch_ease_label(ease),
        "flesch_kincaid_grade": grade,
        "passive_count": total_passives,
        "passive_per_sentence": round(total_passives / n_sentences, 2) if n_sentences else 0.0,
        "total_flags": total_flags,
    }

    quality_notes = _quality_notes(metrics, doc_notes)

    return {
        "sentences": analyzed,
        "metrics": metrics,
        "doc_notes": doc_notes,
        "quality_notes": quality_notes,
        "disclaimer": DISCLAIMER,
    }


def _quality_notes(metrics: dict, doc_notes: list[dict]) -> list[str]:
    """Plain-language writing-quality observations (no invented scores)."""
    notes = []
    ease = metrics["flesch_reading_ease"]
    notes.append(
        f"Readability: Flesch Reading Ease {ease} "
        f"(“{metrics['flesch_ease_label']}”), grade level "
        f"~{metrics['flesch_kincaid_grade']}."
    )
    avg = metrics["avg_sentence_length"]
    if avg > 25:
        notes.append(
            f"Clarity: average sentence length is {avg} words — above the "
            "20–25 word comfort zone for general readers. Shortening the "
            "longest sentences would help."
        )
    elif avg and avg < 12:
        notes.append(
            f"Clarity: average sentence length is {avg} words — short and "
            "punchy, but watch for choppiness if every sentence is brief."
        )
    else:
        notes.append(
            f"Clarity: average sentence length is {avg} words — within a "
            "comfortable range."
        )
    if metrics["passive_per_sentence"] > 0.4:
        notes.append(
            "Conciseness: passive constructions are frequent; converting the "
            "clear ones to active voice usually tightens prose."
        )
    rep = [n for n in doc_notes if n["type"] in ("repetition", "opener_repetition")]
    if rep:
        notes.append(
            f"Variety: {len(rep)} repetition note(s) — varying repeated "
            "words and openers improves flow."
        )
    form = [n for n in doc_notes if n["type"] == "formality"]
    if form:
        notes.append(
            "Tone: some formal/wordy phrasing detected — plainer equivalents "
            "are suggested per sentence."
        )
    return notes
