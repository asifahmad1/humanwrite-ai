"""Low-level NLP utilities for HumanWrite AI v1.

All functions are local, deterministic heuristics. They measure *stylistic*
properties of text only. Nothing here establishes authorship, and nothing
here claims to detect AI-generated content — see analyzer.py for the
honesty framing that wraps these utilities.
"""

from __future__ import annotations

import re
from collections import Counter

# ---------------------------------------------------------------------------
# sentence segmentation (abbreviation-aware)
# ---------------------------------------------------------------------------

_ABBREVIATIONS = {
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "etc", "fig",
    "eq", "al", "no", "pp", "vol", "ch", "sec", "ref", "approx", "appt",
    "dept", "univ", "inc", "ltd", "corp", "co", "e.g", "i.e", "u.s", "u.k",
}

_PLACEHOLDER = "\uE000"  # private-use char, never in real text


def _protect_abbreviations(text: str) -> str:
    """Protect abbreviation periods so segmentation ignores them.

    A period is *kept* (not protected) when it ends a single-letter
    abbreviation chain at a likely sentence boundary, e.g. the final
    period in "U.S. They left." — otherwise "U.S." would swallow the
    sentence break.
    """
    out: list[str] = []
    last = 0
    for m in re.finditer(r"\b([A-Za-z]{1,4})\.", text):
        word = m.group(1)
        low = word.lower()
        is_abbr = low in _ABBREVIATIONS or len(word) == 1
        boundary_after = bool(re.match(r"\s+[\"'“‘(\[]?[A-Z0-9]", text[m.end():]))
        keep_period = len(word) == 1 and boundary_after
        out.append(text[last:m.start()])
        if is_abbr and not keep_period:
            out.append(word + _PLACEHOLDER)
        else:
            out.append(m.group(0))
        last = m.end()
    out.append(text[last:])
    return "".join(out)


def split_sentences(text: str) -> list[dict]:
    """Split text into sentences: [{text, start, end}] with char offsets."""
    text = (text or "").strip()
    if not text:
        return []
    protected = _protect_abbreviations(text)
    # Split on sentence-ending punctuation followed by whitespace + capital/quote/digit.
    parts = re.split(r"(?<=[.!?])\s+(?=[\"'“‘(\[]?[A-Z0-9])", protected)
    sentences = []
    cursor = 0
    for part in parts:
        raw = part.replace(_PLACEHOLDER, ".").strip()
        if not raw:
            continue
        start = text.find(raw[:30], cursor)
        if start < 0:
            start = cursor
        sentences.append({"text": raw, "start": start, "end": start + len(raw)})
        cursor = start + len(raw)
    # Merge fragments that are clearly not sentences (e.g. single abbreviations).
    merged: list[dict] = []
    for s in sentences:
        words = s["text"].split()
        if merged and len(words) <= 2 and not re.search(r"[.!?]$", s["text"]):
            merged[-1]["text"] += " " + s["text"]
            merged[-1]["end"] = s["end"]
        else:
            merged.append(s)
    return merged


def split_paragraphs(text: str) -> list[str]:
    """Split on blank lines; fall back to single paragraph."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]
    return paras or ([text.strip()] if (text or "").strip() else [])


_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z]+)?")


def words(text: str) -> list[str]:
    return _WORD_RE.findall(text or "")


# ---------------------------------------------------------------------------
# syllables + readability (Flesch)
# ---------------------------------------------------------------------------

_VOWELS = set("aeiouy")


def count_syllables(word: str) -> int:
    """Heuristic syllable count for English words."""
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    if len(w) <= 3:
        return 1
    count = 0
    prev_vowel = False
    for ch in w:
        is_vowel = ch in _VOWELS
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel
    if w.endswith("e"):
        count -= 1
    if w.endswith("le") and len(w) > 2 and w[-3] not in _VOWELS:
        count += 1
    if w.endswith("ed") and len(w) > 3 and w[-3] not in _VOWELS:
        count -= 1
    return max(count, 1)


def flesch_reading_ease(n_words: int, n_sentences: int, n_syllables: int) -> float:
    if n_words == 0 or n_sentences == 0:
        return 0.0
    return round(
        206.835 - 1.015 * (n_words / n_sentences) - 84.6 * (n_syllables / n_words), 1
    )


def flesch_kincaid_grade(n_words: int, n_sentences: int, n_syllables: int) -> float:
    if n_words == 0 or n_sentences == 0:
        return 0.0
    return round(
        0.39 * (n_words / n_sentences) + 11.8 * (n_syllables / n_words) - 15.59, 1
    )


def flesch_ease_label(score: float) -> str:
    if score >= 90:
        return "Very easy to read"
    if score >= 80:
        return "Easy to read"
    if score >= 70:
        return "Fairly easy to read"
    if score >= 60:
        return "Standard"
    if score >= 50:
        return "Fairly difficult"
    if score >= 30:
        return "Difficult"
    return "Very difficult"


# ---------------------------------------------------------------------------
# passive voice
# ---------------------------------------------------------------------------

_BE_VERBS = r"(?:am|is|are|was|were|be|been|being)"

_IRREGULAR_PARTICIPLES = {
    "written", "taken", "given", "done", "made", "known", "shown", "grown",
    "drawn", "driven", "spoken", "broken", "chosen", "frozen", "forgotten",
    "hidden", "ridden", "risen", "shaken", "stolen", "torn", "worn", "begun",
    "sung", "sunk", "sworn", "bound", "found", "wound", "taught", "thought",
    "bought", "brought", "caught", "fought", "sought", "built", "sent",
    "spent", "lent", "meant", "dealt", "felt", "kept", "slept", "swept",
    "lost", "shot", "shut", "split", "spread", "cut", "hit", "hurt", "put",
    "set", "quit",
}

_PARTICIPLE = r"(?:\w+(?:ed|en)|" + "|".join(sorted(_IRREGULAR_PARTICIPLES)) + r")"

_PASSIVE_RE = re.compile(
    rf"\b({_BE_VERBS})\b\s+(?:\w+ly\s+)?\b({_PARTICIPLE})\b", re.IGNORECASE
)


def find_passives(sentence: str) -> list[dict]:
    """Return [{phrase, be_verb, participle}] for passive-voice constructions."""
    hits = []
    for m in _PASSIVE_RE.finditer(sentence or ""):
        phrase = m.group(0)
        # Skip adjective-like uses ("is interested", "was tired") only when
        # clearly not verbal — keep the heuristic simple and honest.
        hits.append({
            "phrase": phrase,
            "be_verb": m.group(1),
            "participle": m.group(2),
            "start": m.start(),
            "end": m.end(),
        })
    return hits


# ---------------------------------------------------------------------------
# transition phrases (overuse signals)
# ---------------------------------------------------------------------------

# (phrase, weight) — weight reflects how strongly the phrase is associated
# with formulaic/AI-style writing in style guides. Neutral connectors have
# low weight; inflated academic filler has high weight.
TRANSITION_PHRASES: list[tuple[str, float]] = [
    ("it is important to note that", 1.0),
    ("it should be noted that", 1.0),
    ("it is worth noting that", 0.9),
    ("in today's fast-paced world", 1.0),
    ("in today's world", 0.9),
    ("in this day and age", 0.9),
    ("needless to say", 0.8),
    ("last but not least", 0.8),
    ("in conclusion", 0.7),
    ("to summarize", 0.7),
    ("in summary", 0.6),
    ("furthermore", 0.7),
    ("moreover", 0.7),
    ("in addition", 0.5),
    ("additionally", 0.5),
    ("nevertheless", 0.5),
    ("nonetheless", 0.5),
    ("consequently", 0.6),
    ("accordingly", 0.5),
    ("therefore", 0.4),
    ("thus", 0.4),
    ("hence", 0.5),
    ("however", 0.3),
    ("on the other hand", 0.5),
    ("in contrast", 0.5),
    ("conversely", 0.6),
    ("similarly", 0.4),
    ("likewise", 0.4),
    ("in other words", 0.5),
    ("that is to say", 0.6),
    ("for example", 0.3),
    ("for instance", 0.4),
    ("as a result", 0.4),
    ("for this reason", 0.5),
    ("in this regard", 0.6),
    ("with regard to", 0.6),
    ("in regard to", 0.6),
    ("ultimately", 0.5),
    ("overall", 0.4),
    ("firstly", 0.6),
    ("secondly", 0.6),
    ("thirdly", 0.6),
    ("lastly", 0.5),
    ("importantly", 0.6),
    ("notably", 0.5),
    ("significantly", 0.4),
    ("crucially", 0.6),
    ("essentially", 0.5),
    ("fundamentally", 0.5),
    ("basically", 0.6),
    ("in fact", 0.3),
    ("indeed", 0.4),
]


def find_transitions(sentence: str) -> list[dict]:
    """Return [{phrase, weight}] for transition phrases found in the sentence."""
    lowered = f" {(sentence or '').lower()} "
    hits = []
    for phrase, weight in TRANSITION_PHRASES:
        if f" {phrase} " in lowered or f" {phrase}," in lowered:
            hits.append({"phrase": phrase, "weight": weight})
    return hits


# ---------------------------------------------------------------------------
# formality / wordiness signals: formal word -> plainer alternative
# ---------------------------------------------------------------------------

FORMAL_SWAPS: dict[str, str | None] = {
    "utilize": "use", "utilizes": "uses", "utilized": "used", "utilizing": "using",
    "facilitate": "help", "facilitates": "helps", "facilitated": "helped",
    "facilitating": "helping",
    "leverage": "use", "leverages": "uses", "leveraged": "used",
    "plethora": "large number", "myriad": "many",
    "numerous": "many",
    "implement": "carry out", "implemented": "carried out",
    "commence": "start", "commenced": "started",
    "terminate": "end", "terminated": "ended",
    "obtain": "get", "obtained": "got",
    "acquire": "gain", "acquired": "gained",
    "require": "need", "requires": "needs", "required": "needed",
    "request": "ask", "requested": "asked",
    "inquire": "ask", "inquired": "asked",
    "purchase": "buy", "purchased": "bought",
    "assist": "help", "assisted": "helped",
    "inform": "tell", "informed": "told",
    "demonstrate": "show", "demonstrates": "shows", "demonstrated": "showed",
    "indicate": "show", "indicates": "shows", "indicated": "showed",
    "illustrate": "show", "illustrates": "shows",
    "establish": "set up", "established": "set up",
    "conduct": "carry out", "conducted": "carried out",
    "perform": "do", "performed": "did",
    "endeavor": "try", "endeavour": "try",
    "ascertain": "find out",
    "methodologies": "methods", "methodology": "method",
    "landscape": None,  # handled via phrase swaps ("educational landscape")
}

PHRASE_SWAPS: list[tuple[str, str]] = [
    ("in order to", "to"),
    ("due to the fact that", "because"),
    ("in spite of the fact that", "although"),
    ("despite the fact that", "although"),
    ("prior to", "before"),
    ("subsequent to", "after"),
    ("in the event that", "if"),
    ("at this point in time", "now"),
    ("in the near future", "soon"),
    ("a large number of", "many"),
    ("a wide variety of", "many"),
    ("a variety of", "many"),
    ("with regard to", "about"),
    ("in regard to", "about"),
    ("the educational landscape", "education"),
    ("educational landscape", "education"),
    ("learning experiences", "learning"),
    ("teaching methodologies", "teaching methods"),
    ("innovative opportunities", "new opportunities"),
    ("numerous innovative opportunities", "many new opportunities"),
]

FILLER_WORDS = {
    "very", "really", "quite", "rather", "basically", "actually",
    "simply", "just", "totally", "extremely",
}


def find_formality(sentence: str) -> list[dict]:
    """Return [{kind, match, suggestion}] for formal/filler wording."""
    hits = []
    lowered = f" {(sentence or '').lower()} "
    for phrase, plain in PHRASE_SWAPS:
        if f" {phrase} " in lowered or f" {phrase}," in lowered:
            hits.append({"kind": "phrase", "match": phrase, "suggestion": plain})
    for w in words(sentence):
        low = w.lower()
        if low in FORMAL_SWAPS and FORMAL_SWAPS[low]:
            hits.append({"kind": "word", "match": w, "suggestion": FORMAL_SWAPS[low]})
        elif low in FILLER_WORDS:
            hits.append({"kind": "filler", "match": w,
                         "suggestion": "(consider removing)"})
    return hits


# ---------------------------------------------------------------------------
# repetition
# ---------------------------------------------------------------------------

def repeated_trigrams(sentences: list[str], min_count: int = 2) -> list[dict]:
    """Find 3-word sequences repeated across sentences (case-insensitive)."""
    counts: Counter = Counter()
    for s in sentences:
        toks = [w.lower() for w in words(s)]
        seen = set()
        for i in range(len(toks) - 2):
            tri = " ".join(toks[i:i + 3])
            if tri not in seen:
                counts[tri] += 1
                seen.add(tri)
    return [
        {"phrase": tri, "count": c}
        for tri, c in counts.most_common()
        if c >= min_count and len(tri) > 6
    ]


def sentence_openers(sentences: list[str]) -> Counter:
    """Count first content words of sentences (for opener-repetition checks)."""
    openers: Counter = Counter()
    for s in sentences:
        toks = words(s)
        if toks:
            openers[toks[0].lower()] += 1
    return openers


# ---------------------------------------------------------------------------
# basic local grammar-ish checks (honest scope: not a full grammar checker)
# ---------------------------------------------------------------------------

def basic_checks(text: str) -> list[dict]:
    """Return [{type, detail}] for simple mechanical issues found locally."""
    notes = []
    if re.search(r"\b(\w+)\s+\1\b", text, re.IGNORECASE):
        m = re.search(r"\b(\w+)\s+\1\b", text, re.IGNORECASE)
        notes.append({"type": "repeated_word",
                      "detail": f"Possible repeated word: “{m.group(0)}”."})
    if re.search(r"\s{2,}", text):
        notes.append({"type": "spacing",
                      "detail": "Multiple consecutive spaces found."})
    if re.search(r"\s+[,.!?;:]", text):
        notes.append({"type": "spacing",
                      "detail": "Space before punctuation found."})
    return notes
