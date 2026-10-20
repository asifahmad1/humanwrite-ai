"""Offline rewriting engine for HumanWrite AI v1.

Rule-based, deterministic, and honest: it applies explicit, inspectable
transformations (plain-word swaps, filler removal, passive-to-active,
sentence splitting, contraction use per mode). Every change is reported in
`notes` so the UI can show *what* changed and *why*.

Protected spans — numbers, citation markers, and quoted text — are masked
before rewriting and restored afterwards, so they are never altered.

Ten modes and five intensity levels shape which transforms apply and how
aggressively. Nothing is hard-coded per input; all behaviour comes from
these rules.
"""

from __future__ import annotations

import re

from nlp import FORMAL_SWAPS, PHRASE_SWAPS, FILLER_WORDS, words

MODES: dict[str, dict] = {
    "natural": {
        "name": "Natural Human Writing",
        "description": "Improve fluency and naturalness while preserving meaning.",
    },
    "academic": {
        "name": "Academic Humanization",
        "description": "Precise, natural academic language; keeps scientific "
                       "terminology, evidence and references intact.",
    },
    "professional": {
        "name": "Professional Writing",
        "description": "Polished, concise business communication without "
                       "excessive formality.",
    },
    "conversational": {
        "name": "Conversational Style",
        "description": "Friendly, approachable, natural writing.",
    },
    "simple": {
        "name": "Simple English",
        "description": "Straightforward vocabulary and easy-to-follow sentences.",
    },
    "creative": {
        "name": "Creative Writing",
        "description": "More varied, expressive phrasing; keeps imagery and intent.",
    },
    "native": {
        "name": "Native-Level English Editing",
        "description": "Refine grammar, word choice and natural idiomatic usage.",
    },
    "voice": {
        "name": "Personal Voice Preservation",
        "description": "Minimal edits — only clear improvements, keeping your "
                       "tone and rhythm.",
    },
    "technical": {
        "name": "Technical Writing",
        "description": "Preserve precise terminology; improve clarity and "
                       "logical structure.",
    },
    "minimal": {
        "name": "Minimal Changes",
        "description": "Edit only passages that demonstrably benefit from "
                       "improvement.",
    },
}

INTENSITY_LABELS = {
    1: "Very Light — minor grammar and readability fixes",
    2: "Light — fix awkward wording, keep structure",
    3: "Balanced — improve flow, vocabulary and coherence",
    4: "Strong — substantially revise prose, preserve facts",
    5: "Comprehensive — reconstruct at paragraph level",
}

# ---------------------------------------------------------------------------
# protected spans: numbers, citations, quotations
# ---------------------------------------------------------------------------

_MASK = "\uE001"

_PROTECTED_PATTERNS = [
    # Quoted text (double quotes).
    re.compile(r'"[^"\n]{1,200}"'),
    # Citation markers: [1], [12], (Author, 2020), (Author et al., 2020).
    re.compile(r"\[\d+(?:\s*[-–,]\s*\d+)*\]"),
    re.compile(r"\([A-Z][A-Za-z\-']+(?:\s+et\s+al\.)?,\s*\d{4}[a-z]?\)"),
    # Numbers with units / decimals / percentages / ranges.
    re.compile(rf"(?<!{_MASK})\b\d+(?:\.\d+)?\s*(?:%|mg|g|kg|ml|l|cm|mm|km|°C|°F|h|min|s)\b", re.I),
    # Plain numbers — never touch digits inside an existing mask marker.
    re.compile(rf"(?<!{_MASK})\b\d+(?:\.\d+)?\b(?!{_MASK})"),
]


def mask_protected(text: str) -> tuple[str, list[str]]:
    """Replace protected spans with masks; return (masked, originals)."""
    originals: list[str] = []

    def _save(m: re.Match) -> str:
        originals.append(m.group(0))
        return f"{_MASK}{len(originals) - 1}{_MASK}"

    masked = text
    for pat in _PROTECTED_PATTERNS:
        masked = pat.sub(_save, masked)
    return masked, originals


def unmask_protected(text: str, originals: list[str]) -> str:
    def _restore(m: re.Match) -> str:
        idx = int(m.group(1))
        return originals[idx] if 0 <= idx < len(originals) else m.group(0)
    return re.sub(f"{_MASK}(\\d+){_MASK}", _restore, text)


# ---------------------------------------------------------------------------
# transform primitives (each returns (new_text, note|None))
# ---------------------------------------------------------------------------

def _word_boundary_re(word: str) -> re.Pattern:
    return re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)


def _match_case(template: str, replacement: str) -> str:
    if template[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def t_phrase_swaps(text: str) -> tuple[str, list[str]]:
    notes = []
    for phrase, plain in PHRASE_SWAPS:
        pat = re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE)

        def _sub(m: re.Match) -> str:
            notes.append(f"Simplified “{m.group(0)}” → “{plain}”.")
            return _match_case(m.group(0), plain)

        text = pat.sub(_sub, text)
    return text, notes


def t_word_swaps(text: str) -> tuple[str, list[str]]:
    notes = []
    for formal, plain in FORMAL_SWAPS.items():
        if not plain:
            continue
        pat = _word_boundary_re(formal)

        def _sub(m: re.Match, _plain=plain, _formal=formal) -> str:
            notes.append(f"Used plainer word: “{m.group(0)}” → “{_plain}”.")
            return _match_case(m.group(0), _plain)

        text = pat.sub(_sub, text)
    return text, notes


def t_filler_removal(text: str) -> tuple[str, list[str]]:
    notes = []
    # Drop "It is (important|worth noting|... ) that X" -> "X".
    pat = re.compile(
        r"\b[Ii]t\s+is\s+(?:important\s+to\s+note\s+that|worth\s+noting\s+that|"
        r"noted\s+that|important\s+that)\s+", re.IGNORECASE
    )
    text, n = pat.subn("", text)
    if n:
        notes.append("Removed empty framing (“it is important to note that …”).")
    for filler in sorted(FILLER_WORDS):
        # Only remove fillers before adjectives/adverbs/verbs, never alone.
        fpat = re.compile(rf"\b{re.escape(filler)}\b\s+(?=[a-z])", re.IGNORECASE)
        text, n = fpat.subn("", text)
        if n:
            notes.append(f"Removed filler word “{filler}”.")
    return text, notes


_PASSIVE_BY_RE = re.compile(
    r"\b([A-Z][\w\s,'-]{1,60}?)\s+"
    r"(was|were|is|are)\s+"
    r"(\w+ed|\w+en|written|taken|given|done|made|known|shown|grown|drawn|"
    r"driven|spoken|broken|chosen|taught|thought|bought|brought|built|sent|"
    r"spent|found|lost|cut|set|put)\s+by\s+([^.,;]+)",
    re.IGNORECASE,
)


def t_passive_to_active(text: str) -> tuple[str, list[str]]:
    """Convert 'X was verbed by Y' -> 'Y verbed X' (regular -ed verbs)."""
    notes = []

    def _sub(m: re.Match) -> str:
        subj, be, verb, agent = m.group(1), m.group(2), m.group(3), m.group(4).strip()
        if not verb.lower().endswith(("ed", "en")):
            return m.group(0)  # irregulars: leave alone (safer)
        # Tense mapping for regular verbs.
        past = verb
        new = f"{agent} {past} {subj.strip()}"
        notes.append(f"Active voice: “{m.group(0).strip()}” → “{new.strip()}”.")
        return new

    return _PASSIVE_BY_RE.sub(_sub, text), notes


_SPLIT_RES = [
    re.compile(r";\s+"),
    re.compile(r",\s+which\s+", re.IGNORECASE),
    re.compile(r",\s+and\s+(?=[a-z])"),
]


def t_split_long(text: str, max_words: int = 28) -> tuple[str, list[str]]:
    """Split over-long sentences at safe joints; capitalize new starts."""
    if len(words(text)) <= max_words:
        return text, []
    for pat in _SPLIT_RES:
        if pat.search(text):
            parts = [p.strip(" ,") for p in pat.split(text, maxsplit=1)]
            parts = [p for p in parts if p]
            if len(parts) == 2 and all(len(words(p)) >= 5 for p in parts):
                second = parts[1]
                # Ensure the second half is a full clause before splitting.
                if re.match(r"^(it|they|he|she|we|this|that|these|those)\b", second, re.I) or \
                        re.match(r"^[A-Z]", second):
                    fixed = parts[0].rstrip(",;") + ". " + second[:1].upper() + second[1:]
                    return fixed, ["Split a long sentence into two for readability."]
    return text, []


_CONTRACTIONS = {
    "do not": "don't", "does not": "doesn't", "did not": "didn't",
    "is not": "isn't", "are not": "aren't", "was not": "wasn't",
    "were not": "weren't", "have not": "haven't", "has not": "hasn't",
    "had not": "hadn't", "will not": "won't", "would not": "wouldn't",
    "should not": "shouldn't", "could not": "couldn't", "cannot": "can't",
    "it is": "it's", "that is": "that's", "there is": "there's",
    "you are": "you're", "we are": "we're", "they are": "they're",
}


def t_contractions(text: str) -> tuple[str, list[str]]:
    notes = []
    for full, short in _CONTRACTIONS.items():
        pat = re.compile(rf"\b{re.escape(full)}\b", re.IGNORECASE)
        text, n = pat.subn(lambda m: _match_case(m.group(0), short), text)
        if n:
            notes.append("Used natural contractions (conversational mode).")
            break
    return text, notes


_AI_NOUN_SWAP = [
    (re.compile(r"\bArtificial intelligence\b"), "AI"),
]


def t_ai_abbreviation(text: str, first_use: bool) -> tuple[str, list[str]]:
    """Use 'AI' after the first mention of 'Artificial intelligence'."""
    if first_use:
        return text, []
    new_text, n = _AI_NOUN_SWAP[0][0].subn("AI", text)
    if n:
        return new_text, ["Shortened repeated “Artificial intelligence” to “AI”."]
    return text, []


def _fix_spacing(text: str) -> str:
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    text = re.sub(r"([.!?])\s*([.!?])", r"\1", text)
    return text.strip()


# ---------------------------------------------------------------------------
# mode x intensity pipeline
# ---------------------------------------------------------------------------

def _pipeline_for(mode: str, intensity: int) -> list:
    """Return the ordered transform functions for a mode/intensity."""
    pipe = []
    # Word-level simplification applies in most modes from intensity 2,
    # and in gentle modes even at 1.
    if intensity >= 2 or mode in ("simple", "natural", "conversational"):
        pipe.append(t_phrase_swaps)
        pipe.append(t_word_swaps)
    if intensity >= 2:
        pipe.append(t_filler_removal)
    if intensity >= 3 and mode not in ("voice", "minimal", "technical", "academic"):
        pipe.append(t_passive_to_active)
    elif intensity >= 4 and mode in ("technical", "academic"):
        pipe.append(t_passive_to_active)
    if mode == "conversational":
        pipe.append(t_contractions)
    return pipe


def rewrite_sentence_offline(sentence: str, mode: str, intensity: int,
                             first_use: bool = True) -> tuple[str, list[str]]:
    """Rewrite one sentence offline. Returns (rewritten, notes)."""
    mode = mode if mode in MODES else "natural"
    intensity = max(1, min(5, int(intensity or 3)))

    masked, originals = mask_protected(sentence)
    text = masked
    notes: list[str] = []

    # Minimal / voice modes: only the safest single pass.
    if mode in ("minimal", "voice") and intensity <= 2:
        text, n = t_phrase_swaps(text)
        notes.extend(n)
        text = _fix_spacing(unmask_protected(text, originals))
        return (text, notes) if text != sentence else (sentence, [])

    for transform in _pipeline_for(mode, intensity):
        text, n = transform(text)
        notes.extend(n)

    if mode == "simple" or intensity >= 4:
        text, n = t_split_long(text)
        notes.extend(n)

    if mode in ("academic", "technical") and intensity <= 2:
        # Gentle modes: don't touch terminology-heavy sentences aggressively.
        pass

    text, n = t_ai_abbreviation(text, first_use)
    notes.extend(n)

    text = _fix_spacing(unmask_protected(text, originals))
    if text == sentence:
        return sentence, []
    # Deduplicate notes while keeping order.
    seen, uniq = set(), []
    for n_ in notes:
        if n_ not in seen:
            seen.add(n_)
            uniq.append(n_)
    return text, uniq


def rewrite_text_offline(text: str, mode: str = "natural", intensity: int = 3,
                         sentence_indexes: list[int] | None = None) -> list[dict]:
    """Rewrite selected (or all) sentences offline.

    Returns [{index, original, rewritten, notes, changed}]. Unselected
    sentences are not included — the caller keeps them unchanged.
    """
    from nlp import split_sentences  # local import to avoid cycles
    sentences = split_sentences(text)
    selected = set(sentence_indexes) if sentence_indexes else set(range(len(sentences)))
    seen_ai = False
    results = []
    for i, s in enumerate(sentences):
        if i not in selected:
            continue
        first_use = not seen_ai
        rewritten, notes = rewrite_sentence_offline(
            s["text"], mode, intensity, first_use=first_use)
        if re.search(r"\bArtificial intelligence\b|\bAI\b", s["text"]):
            seen_ai = True
        results.append({
            "index": i,
            "original": s["text"],
            "rewritten": rewritten,
            "notes": notes,
            "changed": rewritten != s["text"],
        })
    return results
